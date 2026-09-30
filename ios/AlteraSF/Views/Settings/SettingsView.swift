import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var name: String = ""
    @State private var email: String = ""
    @State private var isSavingProfile = false
    @State private var profileError: String? = nil
    @State private var showChangePassword = false

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
                    Text(profileError).foregroundColor(AppTheme.danger).font(.figtree(size: 13))
                }
            }

            Section {
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("New applicant applies")
                        Text("Get an email when someone applies").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Daily applicant summary")
                        Text("A digest of the day's applicants").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Weekly hiring report")
                        Text("Performance summary every Monday").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Job post expiring soon")
                        Text("Remind me 3 days before a post closes").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Candidate flagged for review")
                        Text("Integrity alerts from AI screening").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
                Toggle(isOn: .constant(false)) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Product news & tips")
                        Text("Occasional updates from AlteraSF").font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
            } header: {
                Text("Email Notifications")
            } footer: {
                Text("Email notifications aren't available yet. These controls will become available when email delivery is supported.")
            }
            .tint(AppTheme.primary)
            .disabled(true)

            Section("Account") {
                if authVM.canManageHiring {
                    NavigationLink { DepartmentsView() } label: {
                        Label("Departments", systemImage: "folder")
                    }
                }
                if authVM.isAdmin {
                    NavigationLink { TeamView() } label: {
                        Label("Team members", systemImage: "person.3")
                    }
                }
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

        }
        .font(.figtree(size: 16))
        .environment(\.defaultMinListRowHeight, 44)
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppTheme.groupedBackground)
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            name = APIService.shared.currentUser?.fullName ?? ""
            email = authVM.currentUserEmail
        }
        .sheet(isPresented: $showChangePassword) { ChangePasswordView() }
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
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Enter your current password to verify your identity.")
                        .font(.figtree(size: 14)).foregroundColor(AppTheme.textSecondary)
                    passwordField("Current password", text: $current, contentType: .password)
                    passwordField("New password", text: $newPass, contentType: .newPassword)
                    passwordField("Confirm new password", text: $confirm, contentType: .newPassword)
                    Text("At least 8 characters, with a mix of letters and numbers.")
                        .font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    if let error {
                        Text(error).foregroundColor(AppTheme.danger).font(.figtree(size: 13))
                    }
                    Button {
                        guard newPass == confirm else { error = "Passwords do not match."; return }
                        guard newPass.count >= 8 else { error = "Password must be at least 8 characters."; return }
                        Task { await save() }
                    } label: {
                        if isSaving { ProgressView().tint(.white) }
                        else { Text("Update password") }
                    }
                    .buttonStyle(AlteraButtonStyle())
                    .disabled(isSaving)
                }
                .padding(24)
            }
            .background(AppTheme.groupedBackground.ignoresSafeArea())
            .navigationTitle("Change password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
        }
    }

    private func passwordField(_ title: String, text: Binding<String>, contentType: UITextContentType) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.figtree(size: 14, weight: .medium))
            SecureField("••••••••", text: text)
                .textContentType(contentType)
                .textFieldStyle(AlteraTextFieldStyle())
                .accessibilityLabel(title)
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
