import SwiftUI
import GoogleSignIn

@main
struct AlteraSFApp: App {
    @StateObject private var authVM = AuthViewModel(apiService: .shared)
    @StateObject private var apiService = APIService.shared

    init() {
        GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: GoogleAuthConfig.clientID)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authVM)
                .environmentObject(apiService)
                .onAppear { authVM.restoreSession() }
                .onOpenURL { url in
                    GIDSignIn.sharedInstance.handle(url)
                }
        }
    }
}
