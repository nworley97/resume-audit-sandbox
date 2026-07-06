import SwiftUI

struct PrivacyPolicyView: View {
    private var policyURL: URL {
        AppConfig.baseURL.appendingPathComponent("static/legal/20251106_Privacy.pdf")
    }

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "shield.fill")
                .font(.system(size: 40))
                .foregroundColor(AppTheme.primary)

            Text("AlteraSF Privacy Policy")
                .font(.title2.weight(.bold))
                .foregroundColor(AppTheme.textPrimary)

            Text("Our full privacy policy covers what data we collect from candidates and employers, how resumes and assessment answers are stored, and your rights to access or delete your data.")
                .font(.subheadline)
                .foregroundColor(AppTheme.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 24)

            Link(destination: policyURL) {
                Text("View Full Policy")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity).frame(height: 48)
                    .background(AppTheme.primary)
                    .cornerRadius(AppTheme.buttonCornerRadius)
            }
            .padding(.horizontal, 24)
            .padding(.top, 8)

            Spacer()
        }
        .padding(.top, 48)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle("Privacy Policy")
        .navigationBarTitleDisplayMode(.inline)
    }
}
