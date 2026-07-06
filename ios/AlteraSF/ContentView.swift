import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @AppStorage("appearance_mode") private var appearanceModeRaw = AppearanceMode.system.rawValue

    var body: some View {
        Group {
            if authVM.isAuthenticated {
                MainTabView()
            } else {
                SignInView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: authVM.isAuthenticated)
        .preferredColorScheme((AppearanceMode(rawValue: appearanceModeRaw) ?? .system).colorScheme)
    }
}
