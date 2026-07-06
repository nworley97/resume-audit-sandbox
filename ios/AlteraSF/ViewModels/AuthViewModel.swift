import SwiftUI
import LocalAuthentication

final class AuthViewModel: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    var currentUserEmail: String { apiService.currentUser?.username ?? "" }
    var currentUserInitials: String { apiService.currentUser?.initials ?? "ED" }
    var currentUserName: String {
        guard let user = apiService.currentUser else { return "User" }
        return user.fullName.isEmpty ? user.username : user.fullName
    }
    var currentUserCompany: String { apiService.currentUser?.company ?? "" }

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

    @MainActor
    func updateProfile(fullName: String, email: String, company: String) async throws {
        let profile = try await apiService.updateProfile(fullName: fullName, email: email, company: company)
        apiService.currentUser = APIUser(
            username: profile.username,
            fullName: profile.fullName,
            company: profile.company,
            initials: profile.initials,
            isSuper: apiService.currentUser?.isSuper ?? false,
            tenantSlug: apiService.currentUser?.tenantSlug,
            tenantDisplayName: apiService.currentUser?.tenantDisplayName
        )
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
