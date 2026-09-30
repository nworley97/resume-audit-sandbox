import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var selectedTab = 0
    @State private var visitedTabs: Set<Int> = [0]

    var body: some View {
        ZStack {
            ForEach(0..<4) { index in
                if visitedTabs.contains(index) {
                    tabContent(index)
                        .opacity(selectedTab == index ? 1 : 0)
                        .allowsHitTesting(selectedTab == index)
                        .accessibilityHidden(selectedTab != index)
                        .zIndex(selectedTab == index ? 1 : 0)
                }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) { bottomBar }
        .font(.figtree(size: 16))
        .tint(AppTheme.primary)
    }

    @ViewBuilder private func tabContent(_ index: Int) -> some View {
        switch index {
        case 0: JobPostingsView()
        case 1: CandidatesView()
        case 2: AnalyticsView()
        default: AccountTabView()
        }
    }

    private var bottomBar: some View {
        VStack(spacing: 0) {
            Rectangle().fill(AppTheme.divider).frame(height: 0.5)
            HStack(spacing: 0) {
                tabButton(0, "Jobs", "briefcase")
                tabButton(1, "Candidates", "person.2")
                tabButton(2, "Analytics", "chart.bar")
                tabButton(3, "Account", "person.circle")
            }
            .padding(.top, 8).padding(.bottom, 4)
        }
        .background(AppTheme.pageBackground)
    }

    private func tabButton(_ index: Int, _ title: String, _ icon: String) -> some View {
        Button {
            visitedTabs.insert(index)
            selectedTab = index
        } label: {
            VStack(spacing: 3) {
                if index == 3 {
                    AvatarView(initials: String(authVM.currentUserInitials.prefix(2)), size: 26)
                } else {
                    Image(systemName: icon).font(.system(size: 22))
                        .frame(height: 26)
                }
                Text(title).font(.figtree(size: 11))
            }
            .foregroundColor(selectedTab == index ? AppTheme.primary : AppTheme.textSecondary)
            .frame(maxWidth: .infinity, minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("tab.\(title.lowercased())")
        .accessibilityLabel(title)
        .accessibilityAddTraits(selectedTab == index ? .isSelected : [])
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
                                    .font(.figtree(size: 16, weight: .semibold))
                                    .foregroundColor(AppTheme.textPrimary)
                                Text(authVM.currentUserEmail)
                                    .font(.figtree(size: 13))
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
                                    .font(.figtree(size: 15))
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
                                .font(.figtree(size: 15))
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
                .font(.figtree(size: 12))
                .foregroundColor(accessory == "doc.on.doc" ? AppTheme.primary : AppTheme.textTertiary)
        }
        .font(.figtree(size: 15))
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
