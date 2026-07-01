import SwiftUI
import LocalAuthentication

final class AuthViewModel: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    var currentUserEmail: String { apiService.currentUser?.username ?? "" }
    var currentUserInitials: String { apiService.currentUser?.initials ?? "ED" }
    var currentUserName: String { apiService.currentUser?.username ?? "User" }

    private let apiService: APIService

    init(apiService: APIService = .shared) {
        self.apiService = apiService
    }

    func signIn(email: String, password: String) {
        guard !email.isEmpty, !password.isEmpty else {
            errorMessage = "Please enter your email and password."
            return
        }
        isLoading = true
        errorMessage = nil
        Task { @MainActor in
            defer { isLoading = false }
            do {
                _ = try await apiService.login(email: email, password: password)
                isAuthenticated = true
            } catch APIError.notAuthenticated {
                errorMessage = "Invalid email or password."
            } catch let APIError.httpError(code, msg) {
                errorMessage = code == 401 ? "Invalid email or password." : msg
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    func signOut() {
        Task { @MainActor in
            try? await apiService.logout()
            isAuthenticated = false
        }
    }

    func restoreSession() {
        Task { @MainActor in
            do {
                _ = try await apiService.fetchMe()
                isAuthenticated = true
            } catch {
                isAuthenticated = false
            }
        }
    }

    func authenticateWithBiometrics() {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            return
        }
        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                               localizedReason: "Sign in to AlteraSF") { success, _ in
            DispatchQueue.main.async {
                if success { self.restoreSession() }
            }
        }
    }
}
