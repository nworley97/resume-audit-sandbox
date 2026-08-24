import SwiftUI
import LocalAuthentication
import GoogleSignIn
import UIKit

final class AuthViewModel: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    var currentUserEmail: String { apiService.currentUser?.username ?? "" }
    var currentUserInitials: String { apiService.currentUser?.initials ?? "ED" }
    var currentUserName: String {
        guard let user = apiService.currentUser else { return "User" }
        let name = user.fullName ?? ""
        return name.isEmpty ? user.username : name
    }
    var currentUserCompany: String { apiService.currentUser?.company ?? "" }
    var currentUserRole: String { (apiService.currentUser?.role ?? "viewer").lowercased() }
    var canManageHiring: Bool { currentUserRole == "admin" || currentUserRole == "manager" }
    var isAdmin: Bool { currentUserRole == "admin" || apiService.currentUser?.isSuper == true }

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

    func signInWithGoogle() {
        guard let rootVC = UIApplication.shared.connectedScenes
            .compactMap({ ($0 as? UIWindowScene)?.keyWindow?.rootViewController })
            .first else {
            errorMessage = "Couldn't present Google sign-in."
            return
        }
        isLoading = true
        errorMessage = nil
        GIDSignIn.sharedInstance.signIn(withPresenting: rootVC) { [weak self] result, error in
            guard let self else { return }
            if let error {
                Task { @MainActor in
                    self.isLoading = false
                    self.errorMessage = error.localizedDescription
                }
                return
            }
            guard let idToken = result?.user.idToken?.tokenString else {
                Task { @MainActor in
                    self.isLoading = false
                    self.errorMessage = "Couldn't get Google credentials."
                }
                return
            }
            Task { @MainActor in
                defer { self.isLoading = false }
                do {
                    _ = try await self.apiService.googleSignIn(idToken: idToken)
                    self.isAuthenticated = true
                } catch {
                    self.errorMessage = error.localizedDescription
                }
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
            role: apiService.currentUser?.role ?? "viewer",
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
