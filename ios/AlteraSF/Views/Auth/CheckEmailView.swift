import SwiftUI

struct CheckEmailView: View {
    let onBackToSignIn: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("AlteraSF")
                    .font(.system(size: 20, weight: .bold))
                    .foregroundColor(AppTheme.primary)
                Image(systemName: "envelope.badge.fill")
                    .font(.system(size: 38))
                    .foregroundColor(AppTheme.primary)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 6) {
                    Text("Check your email")
                        .font(AppTheme.pageTitle)
                        .foregroundColor(AppTheme.textPrimary)
                    Text("We sent a password reset link to your inbox. Follow it to set a new password.")
                        .font(.system(size: 14))
                        .foregroundColor(AppTheme.textSecondary)
                }
                Button("Back to sign in", action: onBackToSignIn)
                    .buttonStyle(AlteraButtonStyle())
                    .padding(.top, 12)
            }
            .padding(.horizontal, 24)
            .padding(.top, 40)
        }
        .background(AppTheme.pageBackground.ignoresSafeArea())
    }
}
