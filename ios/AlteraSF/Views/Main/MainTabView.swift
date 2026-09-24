import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            JobPostingsView()
                .tabItem { Label("Jobs", systemImage: "briefcase") }
                .tag(0)
            CandidatesView()
                .tabItem { Label("Candidates", systemImage: "person.2") }
                .tag(1)
            AnalyticsView()
                .tabItem { Label("Analytics", systemImage: "chart.bar.fill") }
                .tag(2)
            AccountTabView()
                .tabItem {
                    Label {
                        Text("Account")
                    } icon: {
                        Image(uiImage: accountAvatar).renderingMode(.original)
                    }
                }
                .tag(3)
        }
        .tint(AppTheme.primary)
    }

    // Tab items are rendered by UIKit; arbitrary SwiftUI avatar views are ignored.
    private var accountAvatar: UIImage {
        let size = CGSize(width: 24, height: 24)
        return UIGraphicsImageRenderer(size: size).image { _ in
            UIColor(AppTheme.primary).setFill()
            UIBezierPath(ovalIn: CGRect(origin: .zero, size: size)).fill()
            let initials = String(authVM.currentUserInitials.prefix(2)) as NSString
            let attributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 10, weight: .semibold),
                .foregroundColor: UIColor.white
            ]
            let textSize = initials.size(withAttributes: attributes)
            initials.draw(at: CGPoint(x: (24 - textSize.width) / 2,
                                      y: (24 - textSize.height) / 2), withAttributes: attributes)
        }
    }
}

struct AccountTabView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @Environment(\.colorScheme) private var colorScheme
    @AppStorage("appearance_mode") private var appearanceModeRaw = AppearanceMode.system.rawValue
    @State private var showCopiedToast = false
    @State private var showSettings = false
    @State private var showHelp = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                AppTopBar()
                PageHeader(title: "Account", subtitle: "Account, billing, and preferences.")
                    .background(AppTheme.pageBackground)
                ScrollView {
                    VStack(spacing: 28) {
                        HStack(spacing: 14) {
                            AvatarView(initials: authVM.currentUserInitials, size: 44)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(authVM.currentUserName)
                                    .font(.system(size: 15, weight: .semibold))
                                    .foregroundColor(AppTheme.textPrimary)
                                Text(authVM.currentUserEmail)
                                    .font(.system(size: 13))
                                    .foregroundColor(AppTheme.textSecondary)
                            }
                            Spacer(minLength: 0)
                        }
                        .padding(16).cardStyle()

                        VStack(spacing: 0) {
                            Button(action: copyBoardLink) {
                                accountRow("Copy job board link", icon: "link", accessory: "doc.on.doc")
                            }
                            .disabled(APIService.shared.tenantSlug == nil)
                            if authVM.isAdmin {
                                rowDivider
                                NavigationLink { BillingView() } label: {
                                    accountRow("Billing", icon: "creditcard")
                                }
                            }
                            rowDivider
                            Button { showSettings = true } label: {
                                accountRow("Account settings", icon: "gearshape")
                            }
                            rowDivider
                            Toggle(isOn: Binding(
                                get: { colorScheme == .dark },
                                set: { appearanceModeRaw = $0 ? AppearanceMode.dark.rawValue : AppearanceMode.light.rawValue }
                            )) {
                                Label("Dark mode", systemImage: "moon")
                                    .font(.system(size: 15))
                                    .foregroundColor(AppTheme.textPrimary)
                            }
                            .tint(AppTheme.primary)
                            .padding(.horizontal, 16).padding(.vertical, 6)
                            rowDivider
                            Button { showHelp = true } label: {
                                accountRow("Help & support", icon: "questionmark.circle")
                            }
                        }
                        .buttonStyle(.plain)
                        .cardStyle()

                        Button { authVM.signOut() } label: {
                            Label("Log out", systemImage: "rectangle.portrait.and.arrow.right")
                                .font(.system(size: 15))
                                .foregroundColor(AppTheme.danger)
                                .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
                                .padding(.horizontal, 16)
                        }
                        .cardStyle()
                    }
                    .padding(.horizontal, 16).padding(.top, 32).padding(.bottom, 24)
                }
                .background(AppTheme.groupedBackground)
            }
            .toolbar(.hidden, for: .navigationBar)
            .overlay(alignment: .bottom) {
                if showCopiedToast {
                    ToastView(message: "Job board link copied")
                        .padding(.bottom, 16)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.2), value: showCopiedToast)
            .sheet(isPresented: $showSettings) {
                NavigationStack {
                    SettingsView()
                        .toolbar { ToolbarItem(placement: .confirmationAction) {
                            Button("Done") { showSettings = false }
                        } }
                }
            }
            .sheet(isPresented: $showHelp) { NavigationStack { HelpSupportView() } }
        }
    }

    private var rowDivider: some View { Divider().padding(.leading, 16) }

    private func accountRow(_ title: String, icon: String, accessory: String = "chevron.right") -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).frame(width: 18)
            Text(title)
            Spacer()
            Image(systemName: accessory)
                .font(.system(size: 12))
                .foregroundColor(accessory == "doc.on.doc" ? AppTheme.primary : AppTheme.textTertiary)
        }
        .font(.system(size: 15))
        .foregroundColor(AppTheme.textPrimary)
        .frame(minHeight: 44)
        .padding(.horizontal, 16)
        .contentShape(Rectangle())
    }

    private func copyBoardLink() {
        guard let slug = APIService.shared.tenantSlug else { return }
        UIPasteboard.general.string = AppConfig.baseURL.appendingPathComponent("\(slug)/jobs").absoluteString
        showCopiedToast = true
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            showCopiedToast = false
        }
    }
}
