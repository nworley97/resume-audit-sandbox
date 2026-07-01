import SwiftUI

struct ContentView: View {
    @EnvironmentObject var authVM: AuthViewModel

    var body: some View {
        Group {
            if authVM.isAuthenticated {
                MainTabView()
            } else {
                SignInView()
            }
        }
        .animation(.easeInOut(duration: 0.3), value: authVM.isAuthenticated)
    }
}
