# Task Resource Manager application

## About

The Task Resource Manager application...

# Application Structure

The application is structuredinto a modular structure with multiple files to make it more maintainable and to avoid hitting token limits.

Here's what each file contains:

### 1. `main.py` - Entry Point

- Contains the `main()` function and application startup code
- Very clean and minimal - just launches the application

### 2. `task_manager.py` - Core Class

- The main `TaskResourceManager` class
- Initializes all components and configuration
- Creates the container frame structure
- Holds shared data and state

### 3. `ui_components.py` - UI-Related Code

- UI creation and drawing functions
- Handles scrolling synchronization
- Manages the resizer between grids
- Drawing and rendering of all visual elements

### 4. `task_operations.py` - Task Functionality

- Task manipulation (create, move, resize)
- Resource loading calculation
- Mouse event handlers for tasks
- Dialog handling for task properties

### 5. `file_operations.py` - File Handling

- Project saving and loading
- File dialog management
- Serialization/deserialization of project data

This modular approach has several advantages:

1. **Better Organization**: Related functionality is grouped together
2. **Easier Maintenance**: Smaller files are easier to understand and modify
3. **Avoids Token Limits**: The code is split across multiple files, which prevents hitting token limits during development
4. **Easier Navigation**: Developers can focus on specific aspects of the application
5. **Better Collaboration**: Multiple people can work on different components simultaneously
6. **Extensibility**: New features can be added by extending existing modules or adding new ones

### How to Run the Application

To run the application with this modular structure:

1. Save all the files in the same directory:

    - `main.py`
    - `task_manager.py`
    - `ui_components.py`
    - `task_operations.py`
    - `file_operations.py`

2. Run the application by executing `main.py`

### How the Components Work Together

The application uses a reference-based architecture:

1. The `TaskResourceManager` instance is created in `main.py`
2. This instance is passed to each component (UI, task operations, file operations)
3. Each component can access the manager's properties and other components
4. This allows for coordinated functionality while maintaining separation of concerns

For example, when the user clicks "Save" in the menu:

- The menu calls `file_ops.save_file()`
- The `file_ops` component accesses the manager's task data
- After saving, it updates the manager's current file path and window title

### Key Improvements in This Design

1. **Clear Responsibility Boundaries**:
    - UI components handle only drawing and user interaction
    - Task operations focus on business logic
    - File operations concentrate on persistence
2. **Reduced Coupling**:
    - Each module depends only on what it needs
    - Changes in one area have minimal impact on others
3. **State Management**:
    - Core state is maintained in the manager
    - Components operate on shared state through the manager reference

This structure not only solves the immediate issue with token limits but also provides a more robust foundation for future development of the Task Resource Manager.