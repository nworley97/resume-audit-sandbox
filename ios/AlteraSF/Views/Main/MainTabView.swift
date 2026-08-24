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
                .tabItem { Label("Analytics", systemImage: "chart.bar") }
                .tag(2)

            AccountTabView()
                .tabItem { AccountTabIcon(initials: authVM.currentUserInitials) }
                .tag(3)
        }
        .tint(AppTheme.primary)
    }
}

struct AccountTabIcon: View {
    let initials: String

    var body: some View {
        Text(initials)
            .font(.system(size: 10, weight: .semibold))
            .foregroundColor(.white)
            .frame(width: 20, height: 20)
            .background(Circle().fill(AppTheme.primary))
    }
}

struct AccountTabView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @AppStorage("appearance_mode") private var appearanceModeRaw = AppearanceMode.system.rawValue
    @State private var showCopiedToast = false
    @State private var showSettings = false
    @State private var showHelp = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                AppTopBar()
                PageHeader(title: "Account", subtitle: "Account, billing, and preferences.")

                List {
                    Section {
                        HStack(spacing: 14) {
                            AvatarView(initials: authVM.currentUserInitials, size: 44)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(authVM.currentUserName).font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                                Text(authVM.currentUserEmail).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }

                    Section {
                        Button {
                            if let slug = APIService.shared.tenantSlug {
                                UIPasteboard.general.string = AppConfig.baseURL.appendingPathComponent("\(slug)/jobs").absoluteString
                            }
                            showCopiedToast = true
                            Task {
                                try? await Task.sleep(nanoseconds: 2_000_000_000)
                                showCopiedToast = false
                            }
                        } label: {
                            Label("Copy job board link", systemImage: "link")
                                .foregroundColor(AppTheme.textPrimary)
                        }
                        if authVM.canManageHiring {
                            NavigationLink { DepartmentsView() } label: {
                                Label("Departments", systemImage: "folder")
                            }
                        }
                        if authVM.isAdmin {
                            NavigationLink { TeamView() } label: {
                                Label("Team members", systemImage: "person.3")
                            }
                            NavigationLink { BillingView() } label: {
                                Label("Billing", systemImage: "creditcard")
                            }
                        }
                        Button {
                            showSettings = true
                        } label: {
                            Label("Account settings", systemImage: "gearshape")
                                .foregroundColor(AppTheme.textPrimary)
                        }
                        Button {
                            appearanceModeRaw = isDark ? AppearanceMode.light.rawValue : AppearanceMode.dark.rawValue
                        } label: {
                            Label(isDark ? "Switch to light mode" : "Switch to dark mode", systemImage: "moon")
                                .foregroundColor(AppTheme.textPrimary)
                        }
                        Button {
                            showHelp = true
                        } label: {
                            Label("Help & support", systemImage: "questionmark.circle")
                                .foregroundColor(AppTheme.textPrimary)
                        }
                    }

                    Section {
                        Button(role: .destructive) {
                            authVM.signOut()
                        } label: {
                            Label("Log out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    }
                }
                .listStyle(.insetGrouped)
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
            .sheet(isPresented: $showSettings) { NavigationStack { SettingsView() } }
            .sheet(isPresented: $showHelp) { NavigationStack { HelpSupportView() } }
        }
    }

    private var isDark: Bool { AppearanceMode(rawValue: appearanceModeRaw) == .dark }
}
