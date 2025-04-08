# Welcome to Our-Planner Documentation

An application for collaboratively working on plans with our team. Planning can take resource availability into account. Timeline visualisation for tasks and resources makes it easy to modify and sense check your plans.

## Why another planning tool?

Good plans are co-created with the team that will do the work. For that digital whiteboarding tools such as Miro & Mural are very helpful to map out features and dependencies.
Invariably the question is going to be asked "When will you be done?".
The team will need to make some estimates of how long the individual tasks are going to take. This requires caputing data on estimates and taking into account the availability of the people required to do the work. The current crop of whiteboarding tools do not make this easy.
Quickly moving araound dependant tasks, with updated durations, on a timeline takes so much effort, it kills collaboration.

There are many excellent commercial tools in the market that could do the job but as a consultant to large enterprises it's not practical to change the existing corporate planning and task management tooling stack. Consequently I needed;

 - a free application as I can't expect the corporate to buy software just for a few teams I work with
 - to keep all the corporate data secure in a locally run application, no cloud service here!
 - to link tasks to the corporate task management tool, like Jira
 - I needed source code to be open for inspection by corporate security professionals

Thus this app is written in Python, which is the data analysts' tool of choice, and should be available in most enterprise user desktop builds. Code is hosted on Github and open for inspection, with releases distributed on PyPi for easy installation.

## Key Features

*   **Task Management:** Create, tasks, and dependencies.
*   **Resource Management:** Allocate resources to tasks.
*   **Timeline Visualization:** View tasks and resources alongside a timeline.

## Video Tour

<iframe width="560" height="315" src="https://www.youtube.com/embed/8Zv98uIOFP0" frameborder="0" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

## Getting Started

To get started with Our-Planner, please refer to the [Getting Started](getting-started.md) guide.

## Source Code Repository

[https://github.com/rnwolf/our-planner](https://github.com/rnwolf/our-planner)