"""
This script automates the process of updating the version number in a Python package, generating a changelog entry, committing the changes to Git, and creating a new release tag.
It also includes commented-out lines for building a package and uploading it to PyPI.
"""

import os
import subprocess
import datetime
import tomllib
import requests
import sys


def get_version():
    with open('pyproject.toml', 'rb') as f:
        pyproject_data = tomllib.load(f)
        return pyproject_data['project']['version']


def get_pypi_version(package_name):
    url = f'https://pypi.org/pypi/{package_name}/json'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['info']['version']
    else:
        return None


def main():
    package_name = 'our-planner'
    published_version = get_pypi_version(package_name)
    next_version = get_version()
    if published_version is None:
        print(
            f'No version found on PyPI. Proceeding with the release of version {next_version}.'
        )
    elif next_version <= published_version:
        if next_version == published_version:
            print(f'Version {next_version} is already published on PyPI.')
        else:
            print(
                f'Version {next_version} is older than the published version {published_version}.'
            )
        return
    else:
        print(
            f'Version {next_version} is newer than the published version {published_version}. Proceeding with the release.'
        )

    today = datetime.date.today().strftime('%Y-%m-%d')

    # Make sure that this file has modified date of today
    # as we expect the chanelog to be update now.
    current_filename = os.path.abspath(__file__)
    last_modified_date = datetime.date.fromtimestamp(os.path.getmtime(current_filename))
    if last_modified_date != datetime.date.today():
        print(
            f'The file {current_filename} was last modified on {last_modified_date}, not today.\nHave you added the changelog to the file?'
        )
        return

    changelog = f"""
    ## [{next_version}] - {today}
    ### Added
    - Enhance: Hithub action not in correct folder. Now in workflow folder named main.yml

    """

    # Assume we are using uv to manage python environment for development
    # make sure we have synec the requirements.txt with pyproject.toml
    # so that user who are not using uv can also install and run app.
    subprocess.run(
        [
            'uv',
            'pip',
            'compile',
            'pyproject.toml',
            '-o',
            'requirements.txt',
        ]
    )

    # assume that pyproject.toml is the master source of the version number
    # we might want to add a bump feature to this script in the future
    # # Update version in setup.py or pyproject.toml
    # with open('pyproject.toml', 'r') as file:
    #     setup_content = file.read()

    # setup_content = re.sub(
    #     r"version=['\"]\d+\.\d+\.\d+['\"]", f"version='{version}'", setup_content
    # )

    # with open('pyproject.toml', 'w') as file:
    #     file.write(setup_content)

    # Update version and release date in src/__init__.py
    init_file_path = os.path.join('.', 'src', '__init__.py')
    if os.path.exists(init_file_path):
        with open(init_file_path, 'r') as f:
            lines = f.readlines()

        with open(init_file_path, 'w') as f:
            for line in lines:
                if line.startswith('__version__'):
                    f.write(f'__version__ = "{next_version}"\n')
                elif line.startswith('__release_date__'):
                    f.write(f'__release_date__ = "{datetime.date.today()}"\n')
                else:
                    f.write(line)
    else:
        print(f'File {init_file_path} does not exist. Creating a new one.')
        with open(init_file_path, 'w') as f:
            f.write(
                '"""Task Resource Manager\n\nA Tkinter application for managing tasks and resources with timeline visualization."""\n\n'
            )
            f.write(f'__version__ = "{next_version}"\n')
            f.write(f'__release_date__ = "{datetime.date.today()}"\n')
            f.write('__author__ = "R.N. Wolf"\n')

    # Update CHANGELOG.md
    if os.path.exists('CHANGELOG.md'):
        with open('CHANGELOG.md', 'r') as file:
            existing_content = file.read()
    else:
        existing_content = ''

    with open('CHANGELOG.md', 'w') as file:
        file.write(changelog + '\n' + existing_content)

    # Ensure we are in the develop branch
    current_branch = subprocess.check_output(
        ['git', 'branch', '--show-current'], text=True
    ).strip()
    if current_branch != 'develop':
        print(
            f'Not in develop branch. Currently {current_branch} In order to release, please checkout the develop branch.'
        )
        sys.exit(1)
    else:
        print('In develop branch. Proceeding with the release process.')

        # Run tests
        print('Run automated Tests. Please wait.')
        result = subprocess.run(
            ['uv', 'run', 'run_tests.py'], capture_output=True, text=True
        )

        if result.returncode != 0:
            print('Tests failed. Aborting release.')
            print(result.stdout)
            print(result.stderr)
            return
        else:
            print('Tests passed. Continuing with the release process.')

            # Check that build runs successfully
            print('Check distribution builds. Please wait.')
            result = subprocess.run(['uv', 'build'], capture_output=True, text=True)
            if result.returncode != 0:
                print('Distribution Build failed. Aborting release.')
                print(result.stdout)
                print(result.stderr)
                return
            else:
                print('Build passed. Continuing with the release process.')

                print(
                    'Add files that change during release process to release. Continuing with the release process.'
                )
                subprocess.run(
                    [
                        'git',
                        'add',
                        'pyproject.toml',
                        'CHANGELOG.md',
                        'README.md',
                        'build.py',
                        r'.\src\__init__.py',
                        'requirements.txt',
                        'uv.lock',
                    ]
                )
                print(
                    'Files added and staged for release. Continuing with the release process.'
                )

                print('Commit staged files. Continuing with the release process.')
                subprocess.run(
                    [
                        'git',
                        'commit',
                        '-m',
                        f'Release version {next_version} on {today}',
                    ]
                )

                print('Creating new release tag')
                subprocess.run(
                    [
                        'git',
                        'tag',
                        '-a',
                        f'v{next_version}',
                        '-m',
                        f'Release version {next_version} on {today}',
                    ]
                )

                print('Pushing tag to remote repo develop branch')
                subprocess.run(['git', 'push', '-u', 'origin', 'develop'])

                print('Merge develop into main branch')
                subprocess.run(['git', 'switch', 'main'])
                subprocess.run(['git', 'merge', 'develop'])

                print('Push code and tags to main branch on the remote repo in GitHub')
                subprocess.run(['git', 'push', '-u', 'origin', 'main', '--tags'])

                # Build and upload package to PyPI (uncomment if needed)
                # Install keyring to secure test.pypi token locally https://pypi.org/project/keyring/
                # See https://github.com/astral-sh/uv/issues/7963 for discussion on how to do a manual release for inital release
                #
                # keyring set https://upload.pypi.org/legacy/?our-planner __token__
                # Note: On MS-Windows you must use the Edit/Paste command in the menu to paste the token into the keyring prompt.
                #
                # uv publish --username __token__ --keyring-provider subprocess --publish-url https://upload.pypi.org/legacy/?our-planner
                #
                # Use github actions to do the release automatically after configuring the token in the github actions secrets after the first manual release
                print(
                    'Github action will be triggered and rebuild the distribution to upload to github and PyPI.\nPlease make sure that the release is successful.'
                )


if __name__ == '__main__':
    main()
