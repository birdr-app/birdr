import ExpoModulesCore
import UIKit

public class SoftwareKeyboardModule: Module {
  public func definition() -> ModuleDefinition {
    Name("SoftwareKeyboard")

    Function("ensureShown") {
      DispatchQueue.main.async {
        Self.ensureKeyWindow()
        Self.showSoftwareKeyboard()
      }
    }
  }

  private static func ensureKeyWindow() {
    let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
    let scene =
      scenes.first(where: { $0.activationState == .foregroundActive })
      ?? scenes.first
    guard let window = scene?.windows.first(where: { !$0.isHidden }) ?? scene?.windows.first else {
      return
    }
    if !window.isKeyWindow {
      window.makeKeyAndVisible()
    }
  }

  /// iPadOS hides the software keyboard when a hardware keyboard is connected.
  /// This private UIApplication action toggles it back on.
  private static func showSoftwareKeyboard() {
    let selector = NSSelectorFromString("toggleSoftwareKeyboard")
    UIApplication.shared.sendAction(selector, to: nil, from: nil, for: nil)
  }
}
