"""
This script automates the process of updating the version number in a Python package, generating a changelog entry, committing the changes to Git, and creating a new release tag.
It also includes commented-out lines for building a package and uploading it to PyPI.
"""

import os
import subprocess
import datetime
import tomllib
import requests


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

    with open('version.py', 'w') as f:
        f.write(f'__version__ = "{next_version}"\n')
        f.write(f'__release_date__ = "{datetime.date.today()}"\n')

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
    - New feature: Build script to help with release process.
    - New feature: Updated pyproject.toml development dependencies for use with UV.

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
        exit(1)
    else:
        print('In develop branch. Proceeding with the release process.')

        # Run tests
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

            subprocess.run(
                [
                    'git',
                    'add',
                    'pyproject.toml',
                    'CHANGELOG.md',
                    'build.py',
                    '.\src\__init__.py',
                    'requirements.txt',
                ]
            )
            subprocess.run(
                ['git', 'commit', '-m', f'Release version {next_version} on {today}']
            )
            subprocess.run(['git', 'push', '-u', 'origin', 'develop'])

            # Merge develop into main
            subprocess.run(['git', 'switch', 'main'])
            subprocess.run(['git', 'merge', 'develop'])

            # Create and push tag
            subprocess.run(
                [
                    'git',
                    'tag',
                    '-a',
                    f'v{next_version}',
                    '-m',
                    f'Release version {next_version}',
                ]
            )
            subprocess.run(['git', 'push', 'origin', f'v{next_version}'])

            # Build and upload package to PyPI (uncomment if needed)


if __name__ == '__main__':
    main()
