package expo.modules.softwarekeyboard

import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

class SoftwareKeyboardModule : Module() {
  override fun definition() = ModuleDefinition {
    Name("SoftwareKeyboard")
    Function("ensureShown") { }
  }
}
