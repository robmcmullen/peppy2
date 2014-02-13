# Standard library imports.
import os.path

# Enthought library imports.
from envisage.api import ExtensionPoint, Plugin
from envisage.ui.tasks.api import TaskFactory
from traits.api import List


class FrameworkPlugin(Plugin):
    """ The sample framework plugin.
    """

    # Extension point IDs.
    PREFERENCES       = 'envisage.preferences'
    PREFERENCES_PANES = 'envisage.ui.tasks.preferences_panes'
    TASKS             = 'envisage.ui.tasks.tasks'

    #### 'IPlugin' interface ##################################################

    # The plugin's unique identifier.
    id = 'peppy.framework'

    # The plugin's name (suitable for displaying to the user).
    name = 'Framework'

    #### Contributions to extension points made by this plugin ################

    preferences = List(contributes_to=PREFERENCES)
    preferences_panes = List(contributes_to=PREFERENCES_PANES)
    tasks = List(contributes_to=TASKS)

    ###########################################################################
    # Protected interface.
    ###########################################################################

    def _preferences_default(self):
        filename = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'preferences.ini')
        return [ 'file://' + filename ]

    def _preferences_panes_default(self):
        from framework_preferences import FrameworkPreferencesPane
        from text_edit import TextEditPreferencesPane
        from image_edit import ImageEditPreferencesPane
        return [ FrameworkPreferencesPane, TextEditPreferencesPane, ImageEditPreferencesPane ]

    def _tasks_default(self):
        from attractors import Visualize2dTask
        from skeleton import SkeletonTask
        from text_edit import TextEditTask
        from image_edit import ImageEditTask

        return [ 
            TaskFactory(id = 'peppy.framework.text_edit',
                        name = 'Text Editor',
                        factory = TextEditTask),

            TaskFactory(id = 'peppy.framework.image_edit',
                        name = 'Image Editor',
                        factory = ImageEditTask),

            TaskFactory(id = 'peppy.framework.skeleton',
                        name = 'Dummy Task',
                        factory = SkeletonTask),

#            TaskFactory(id = 'peppy.framework.task_2d',
#                        name = '2D Visualization',
#                        factory = Visualize2dTask),
            ]
