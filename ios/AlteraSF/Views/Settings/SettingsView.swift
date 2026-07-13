import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var name: String = ""
    @State private var email: String = ""
    @State private var isSavingProfile = false
    @State private var profileError: String? = nil
    @State private var showChangePassword = false
    @State private var showDangerZone = false

    @AppStorage("notif_email") private var notifEmail = true
    @AppStorage("notif_push") private var notifPush = true
    @AppStorage("notif_weekly_digest") private var notifWeeklyDigest = false

    var body: some View {
        List {
            Section("Profile") {
                HStack {
                    Text("Full name").foregroundColor(AppTheme.textSecondary)
                    Spacer()
                    TextField("Your name", text: $name)
                        .multilineTextAlignment(.trailing)
                        .onSubmit { Task { await saveProfile() } }
                }
                HStack {
                    Text("Email").foregroundColor(AppTheme.textSecondary)
                    Spacer()
                    TextField("Email address", text: $email)
                        .multilineTextAlignment(.trailing)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .onSubmit { Task { await saveProfile() } }
                }
                if isSavingProfile {
                    HStack { Spacer(); ProgressView().scaleEffect(0.7); Spacer() }
                }
                if let profileError {
                    Text(profileError).foregroundColor(AppTheme.danger).font(.caption)
                }
            }

            Section("Notifications") {
                Toggle("Email notifications", isOn: $notifEmail)
                Toggle("Push notifications", isOn: $notifPush)
                Toggle("Weekly digest", isOn: $notifWeeklyDigest)
            }
            .tint(AppTheme.primary)

            Section("Account") {
                Button {
                    showChangePassword = true
                } label: {
                    Label("Change password", systemImage: "lock")
                        .foregroundColor(AppTheme.textPrimary)
                }
                NavigationLink {
                    PrivacyPolicyView()
                } label: {
                    Label("Privacy & data", systemImage: "shield")
                }
                NavigationLink {
                    HelpSupportView()
                } label: {
                    Label("Help & support", systemImage: "questionmark.circle")
                }
            }

            // Danger zone
            Section {
                Button(role: .destructive) {
                    showDangerZone = true
                } label: {
                    Label("Delete account", systemImage: "trash")
                }
            } footer: {
                Text("Deleting your account is permanent and cannot be undone.")
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            name = authVM.currentUserName
            email = authVM.currentUserEmail
        }
        .sheet(isPresented: $showChangePassword) { ChangePasswordView() }
        .confirmationDialog("Delete your account?", isPresented: $showDangerZone, titleVisibility: .visible) {
            Button("Delete Account", role: .destructive) { authVM.signOut() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("All your data, jobs, and candidates will be permanently removed.")
        }
    }

    private func saveProfile() async {
        isSavingProfile = true
        profileError = nil
        do {
            try await authVM.updateProfile(fullName: name, email: email, company: authVM.currentUserCompany)
        } catch {
            profileError = error.localizedDescription
        }
        isSavingProfile = false
    }
}


// MARK: – Change Password Sheet

struct ChangePasswordView: View {
    @Environment(\.dismiss) var dismiss
    @State private var current = ""
    @State private var newPass = ""
    @State private var confirm = ""
    @State private var error: String? = nil
    @State private var isSaving = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("Current password", text: $current)
                } footer: {
                    Text("Enter your current password to verify your identity.")
                }
                Section {
                    SecureField("New password", text: $newPass)
                    SecureField("Confirm new password", text: $confirm)
                } header: {
                    Text("New Password")
                } footer: {
                    Text("At least 8 characters, with a mix of letters and numbers.")
                }
                if let err = error {
                    Section {
                        Text(err).foregroundColor(AppTheme.danger).font(.caption)
                    }
                }
            }
            .navigationTitle("Change Password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView().scaleEffect(0.8)
                    } else {
                        Button("Save") {
                            guard newPass == confirm else { error = "Passwords do not match."; return }
                            guard newPass.count >= 8 else { error = "Password must be at least 8 characters."; return }
                            Task { await save() }
                        }
                        .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                    }
                }
            }
        }
    }

    private func save() async {
        isSaving = true
        error = nil
        do {
            try await APIService.shared.changePassword(current: current, new: newPass)
            isSaving = false
            dismiss()
        } catch {
            isSaving = false
            self.error = error.localizedDescription
        }
    }
}
