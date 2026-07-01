import SwiftUI

struct CheckEmailView: View {
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "envelope.badge.fill")
                .font(.system(size: 64))
                .foregroundColor(AppTheme.primary)

            VStack(spacing: 8) {
                Text("Check your email")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)
                Text("We sent a password reset link to your inbox. Follow it to set a new password.")
                    .font(.subheadline)
                    .foregroundColor(AppTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            Spacer()
            Button {
                // Pop to root (sign in)
                dismiss()
                dismiss()
            } label: {
                Text("Back to sign in")
                    .font(.system(size: 16, weight: .semibold))
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
            }
            .background(AppTheme.primary)
            .foregroundColor(.white)
            .cornerRadius(AppTheme.buttonCornerRadius)
            .padding(.horizontal, 24)
            .padding(.bottom, 40)
        }
        .background(AppTheme.background.ignoresSafeArea())
        .navigationBarBackButtonHidden(true)
    }
}
