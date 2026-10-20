# -*- coding: utf-8 -*-
# FC YBT Raytracer -- FreeCAD eklentisi, arayüz başlangıcı.
#   * Komutlar: YBT_Render, YBT_NewScene, YBT_DistantLight, YBT_PointLight, YBT_SpotLight, YBT_LightProperties, YBT_Materials, YBT_Options  (ybt_raytracer/commands.py)
#   * "YBT Raytracer" tezgâhı: tezgâh listesinde kendi adı, ikonu, araç çubuğu ve menüsüyle görünür.
#     Kapatmak için parametre Mod/FCYBTRayTracer/SeparateWorkbench = false (FreeCAD'i yeniden başlatmak gerekir).
#   * Her tezgâhta: standart "Macro" araç çubuğu ve menüsü (FreeCAD 1.0+; kapatmak için parametre
#     Mod/FCYBTRayTracer/ShowInAllWorkbenches = false)
# NOT: FreeCAD bu dosyayı ayrı globals/locals sözlükleriyle çalıştırır; bu yüzden dosyanın üst düzeyinde tanımlanan
# adlar sınıf gövdesinden ve yöntemlerden GÖRÜNMEZ. Sınıf içinde yalnızca yerleşik adlar ve yerel içe aktarmalar kullanılır.
import FreeCAD
import FreeCADGui as Gui

try:
    from ybt_raytracer import commands as _ybt_commands
    _ybt_commands.register()
    _ybt_use_workbench = _ybt_commands.separate_workbench_enabled()
except Exception:
    import traceback
    FreeCAD.Console.PrintError("YBT Raytracer: komutlar kaydedilemedi:\n" + traceback.format_exc())
    _ybt_use_workbench = False

if _ybt_use_workbench:
    class YBTRaytracerWorkbench(Workbench):             # noqa: F821  (Workbench FreeCAD tarafından sağlanır)
        MenuText = "YBT Raytracer"
        ToolTip = "Numpy tabanlı yerleşik ışın izleyici"
        Icon = __import__("ybt_raytracer.commands", fromlist=["icon_path"]).icon_path()

        def Initialize(self):
            from ybt_raytracer import commands as _c
            cmds = list(_c.COMMANDS)
            self.appendToolbar(_c.TOOLBAR, cmds)
            self.appendMenu(_c.MENU, cmds)

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    Gui.addWorkbench(YBTRaytracerWorkbench())
