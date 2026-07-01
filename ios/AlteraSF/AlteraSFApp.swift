import SwiftUI

@main
struct AlteraSFApp: App {
    @StateObject private var authVM = AuthViewModel(apiService: .shared)
    @StateObject private var apiService = APIService.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authVM)
                .environmentObject(apiService)
                .onAppear { authVM.restoreSession() }
        }
    }
}
