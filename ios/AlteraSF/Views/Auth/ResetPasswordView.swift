import SwiftUI

struct ResetPasswordView: View {
    @Environment(\.dismiss) var dismiss
    @State private var email = ""
    @State private var sent = false
    @State private var isSending = false
    @State private var error: String? = nil

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("AlteraSF")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundColor(AppTheme.primary)
                    Text("Reset password")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundColor(AppTheme.textPrimary)
                    Text("Enter the email tied to your account and we'll send you a secure reset link.")
                        .font(.subheadline)
                        .foregroundColor(AppTheme.textSecondary)
                }
                .padding(.top, 40)
                .padding(.bottom, 40)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Email")
                        .font(.subheadline).fontWeight(.medium)
                        .foregroundColor(AppTheme.textPrimary)
                    TextField("you@company.com", text: $email)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .textFieldStyle(AlteraTextFieldStyle())
                }

                if let error {
                    Text(error).font(.caption).foregroundColor(AppTheme.danger).padding(.top, 8)
                }

                Button {
                    Task { await send() }
                } label: {
                    Group {
                        if isSending {
                            ProgressView().tint(.white)
                        } else {
                            Text("Send reset link").font(.system(size: 16, weight: .semibold))
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                }
                .background(AppTheme.primary)
                .foregroundColor(.white)
                .cornerRadius(AppTheme.buttonCornerRadius)
                .disabled(isSending || email.isEmpty)
                .padding(.top, 24)
                .navigationDestination(isPresented: $sent) {
                    CheckEmailView()
                }

                Button("Remembered it? Back to sign in") {
                    dismiss()
                }
                .font(.subheadline)
                .foregroundColor(AppTheme.primary)
                .padding(.top, 16)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarBackButtonHidden(false)
    }

    private func send() async {
        isSending = true
        error = nil
        do {
            try await APIService.shared.forgotPassword(email: email)
            sent = true
        } catch {
            self.error = error.localizedDescription
        }
        isSending = false
    }
}
