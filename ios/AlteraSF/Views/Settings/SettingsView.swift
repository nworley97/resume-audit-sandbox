import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var showEditProfile = false
    @State private var showChangePassword = false
    @State private var showDangerZone = false
    @AppStorage("appearance_mode") private var appearanceModeRaw = AppearanceMode.system.rawValue

    // Notification toggles
    @AppStorage("notif_new_application") var notifNewApplication = true
    @AppStorage("notif_assessment_complete") var notifAssessmentComplete = true
    @AppStorage("notif_diamond_found") var notifDiamondFound = true
    @AppStorage("notif_weekly_summary") var notifWeeklySummary = false
    @AppStorage("notif_job_board_views") var notifJobBoardViews = false

    var body: some View {
        List {
            // Account
            Section("Account") {
                Button {
                    showEditProfile = true
                } label: {
                    HStack(spacing: 14) {
                        ZStack {
                            Circle()
                                .fill(AppTheme.primary)
                                .frame(width: 48, height: 48)
                            Text(authVM.currentUserInitials)
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(.white)
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(authVM.currentUserName)
                                .font(.system(size: 15, weight: .semibold))
                                .foregroundColor(AppTheme.textPrimary)
                            Text(authVM.currentUserEmail)
                                .font(.system(size: 13))
                                .foregroundColor(AppTheme.textSecondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption).foregroundColor(AppTheme.textTertiary)
                    }
                    .padding(.vertical, 4)
                }

                Button {
                    showChangePassword = true
                } label: {
                    Label("Change Password", systemImage: "lock")
                        .foregroundColor(AppTheme.textPrimary)
                }
            }

            // Appearance
            Section("Appearance") {
                Picker("Theme", selection: $appearanceModeRaw) {
                    ForEach(AppearanceMode.allCases) { mode in
                        Text(mode.label).tag(mode.rawValue)
                    }
                }
            }

            // Notifications
            Section("Notifications") {
                Toggle(isOn: $notifNewApplication) {
                    Label("New applications", systemImage: "person.badge.plus")
                }
                Toggle(isOn: $notifAssessmentComplete) {
                    Label("Assessment completed", systemImage: "checkmark.circle")
                }
                Toggle(isOn: $notifDiamondFound) {
                    Label("Diamond candidate found", systemImage: "diamond.fill")
                }
                Toggle(isOn: $notifWeeklySummary) {
                    Label("Weekly summary", systemImage: "chart.bar")
                }
                Toggle(isOn: $notifJobBoardViews) {
                    Label("Job board traffic", systemImage: "megaphone")
                }
            }
            .tint(AppTheme.primary)

            // Workspace
            Section("Workspace") {
                NavigationLink {
                    TeamView()
                } label: {
                    Label("Team members", systemImage: "person.2")
                }
                NavigationLink {
                    DepartmentsView()
                } label: {
                    Label("Departments", systemImage: "building.2")
                }
                NavigationLink {
                    BillingView()
                } label: {
                    Label("Billing & Plans", systemImage: "creditcard")
                }
            }

            // App
            Section("App") {
                HStack {
                    Label("Version", systemImage: "info.circle")
                    Spacer()
                    Text("1.0.0").foregroundColor(AppTheme.textSecondary).font(.system(size: 14))
                }
                NavigationLink {
                    HelpSupportView()
                } label: {
                    Label("Help & Support", systemImage: "questionmark.circle")
                }
                NavigationLink {
                    PrivacyPolicyView()
                } label: {
                    Label("Privacy Policy", systemImage: "shield")
                }
            }

            // Danger zone
            Section {
                Button(role: .destructive) {
                    showDangerZone = true
                } label: {
                    Label("Delete Account", systemImage: "trash")
                }
            } footer: {
                Text("Deleting your account is permanent and cannot be undone.")
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.large)
        .sheet(isPresented: $showEditProfile) { EditProfileView() }
        .sheet(isPresented: $showChangePassword) { ChangePasswordView() }
        .confirmationDialog("Delete your account?", isPresented: $showDangerZone, titleVisibility: .visible) {
            Button("Delete Account", role: .destructive) { authVM.signOut() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("All your data, jobs, and candidates will be permanently removed.")
        }
    }
}

// MARK: – Edit Profile Sheet

struct EditProfileView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authVM: AuthViewModel
    @State private var name: String = ""
    @State private var email: String = ""
    @State private var company: String = ""
    @State private var isSaving = false
    @State private var error: String? = nil

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Spacer()
                        VStack(spacing: 10) {
                            ZStack {
                                Circle().fill(AppTheme.primary).frame(width: 72, height: 72)
                                Text(authVM.currentUserInitials)
                                    .font(.system(size: 24, weight: .bold)).foregroundColor(.white)
                            }
                        }
                        Spacer()
                    }
                    .padding(.vertical, 8)
                    .listRowBackground(Color.clear)
                }

                Section("Personal Information") {
                    HStack {
                        Text("Full name").foregroundColor(AppTheme.textSecondary)
                        Spacer()
                        TextField("Your name", text: $name).multilineTextAlignment(.trailing)
                    }
                    HStack {
                        Text("Email").foregroundColor(AppTheme.textSecondary)
                        Spacer()
                        TextField("Email address", text: $email)
                            .multilineTextAlignment(.trailing)
                            .keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never)
                    }
                    HStack {
                        Text("Company").foregroundColor(AppTheme.textSecondary)
                        Spacer()
                        TextField("Company name", text: $company).multilineTextAlignment(.trailing)
                    }
                }

                if let err = error {
                    Section {
                        Text(err).foregroundColor(AppTheme.danger).font(.caption)
                    }
                }
            }
            .navigationTitle("Edit Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView().scaleEffect(0.8)
                    } else {
                        Button("Save") {
                            Task { await save() }
                        }
                        .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                    }
                }
            }
            .onAppear {
                name = authVM.currentUserName
                email = authVM.currentUserEmail
            }
        }
    }

    private func save() async {
        isSaving = true
        error = nil
        do {
            try await authVM.updateProfile(fullName: name, email: email, company: company)
            isSaving = false
            dismiss()
        } catch {
            isSaving = false
            self.error = error.localizedDescription
        }
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
