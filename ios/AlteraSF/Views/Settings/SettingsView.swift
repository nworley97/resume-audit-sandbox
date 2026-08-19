import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var name: String = ""
    @State private var email: String = ""
    @State private var isSavingProfile = false
    @State private var profileError: String? = nil
    @State private var showChangePassword = false
    @State private var showDangerZone = false

    @AppStorage("notif_new_applicant") private var notifNewApplicant = true
    @AppStorage("notif_daily_summary") private var notifDailySummary = false
    @AppStorage("notif_weekly_report") private var notifWeeklyReport = true
    @AppStorage("notif_job_expiring") private var notifJobExpiring = true
    @AppStorage("notif_candidate_flagged") private var notifCandidateFlagged = true
    @AppStorage("notif_product_news") private var notifProductNews = false

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

            Section {
                Toggle(isOn: $notifNewApplicant) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("New applicant applies")
                        Text("Get an email when someone applies").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: $notifDailySummary) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Daily applicant summary")
                        Text("A digest of the day's applicants").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: $notifWeeklyReport) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Weekly hiring report")
                        Text("Performance summary every Monday").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: $notifJobExpiring) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Job post expiring soon")
                        Text("Remind me 3 days before a post closes").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: $notifCandidateFlagged) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Candidate flagged for review")
                        Text("Integrity alerts from AI screening").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: $notifProductNews) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Product news & tips")
                        Text("Occasional updates from AlteraSF").font(.caption).foregroundColor(AppTheme.textSecondary)
                    }
                }
            } header: {
                Text("Email Notifications")
            } footer: {
                Text("Choose which emails AlteraSF sends you.")
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
