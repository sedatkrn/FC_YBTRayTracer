# -*- coding: utf-8 -*-
# FC YBT Raytracer -- FreeCAD eklentisi, arayüz başlangıcı.
#   * Komutlar: YBT_Render, YBT_Materials, YBT_Defaults  (ybt_raytracer/commands.py)
#   * Her tezgâhta: standart "Macro" araç çubuğu ve menüsü (FreeCAD 1.0+; kapatmak için parametre
#     Mod/FCYBTRayTracer/ShowInAllWorkbenches = false)
#   * İsteğe bağlı ayrı tezgâh "YBT Raytracer": parametre Mod/FCYBTRayTracer/SeparateWorkbench = true
#     (FreeCAD'i yeniden başlatmak gerekir; manipulator'ü olmayan eski FreeCAD'lerde zorunlu açıktır)
import os
import FreeCAD
import FreeCADGui as Gui

try:
    from ybt_raytracer import commands as _ybt_commands
    _ybt_commands.register()
except Exception:
    import traceback
    FreeCAD.Console.PrintError("YBT Raytracer: komutlar kaydedilemedi:\n" + traceback.format_exc())
    _ybt_commands = None

if _ybt_commands is not None and _ybt_commands.separate_workbench_enabled():
    import ybt_raytracer as _ybt_pkg
    _ybt_icon = os.path.join(os.path.dirname(os.path.abspath(_ybt_pkg.__file__)), "icon.png")

    class YBTRaytracerWorkbench(Workbench):             # noqa: F821  (Workbench FreeCAD tarafından sağlanır)
        MenuText = "YBT Raytracer"
        ToolTip = "Numpy tabanlı yerleşik ışın izleyici"
        Icon = _ybt_icon

        def Initialize(self):
            cmds = list(_ybt_commands.COMMANDS)
            self.appendToolbar(_ybt_commands.TOOLBAR, cmds)
            self.appendMenu(_ybt_commands.MENU, cmds)

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    Gui.addWorkbench(YBTRaytracerWorkbench())
