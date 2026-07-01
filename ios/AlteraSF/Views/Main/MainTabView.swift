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

            JobBoardView()
                .tabItem { Label("Job Board", systemImage: "storefront") }
                .tag(3)

            MoreView()
                .tabItem { Label("More", systemImage: "ellipsis") }
                .tag(4)
        }
        .tint(AppTheme.primary)
    }
}

struct MoreView: View {
    @EnvironmentObject var authVM: AuthViewModel

    var body: some View {
        NavigationStack {
            List {
                // Account header
                Section {
                    HStack(spacing: 14) {
                        ZStack {
                            Circle().fill(AppTheme.primary).frame(width: 50, height: 50)
                            Text(authVM.currentUserInitials)
                                .font(.system(size: 17, weight: .bold)).foregroundColor(.white)
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
                        NavigationLink { SettingsView() } label: {
                            Image(systemName: "gear")
                                .font(.system(size: 18))
                                .foregroundColor(AppTheme.textSecondary)
                        }
                    }
                    .padding(.vertical, 4)
                }

                // Manage
                Section("Manage") {
                    NavigationLink { NotificationsView() } label: {
                        Label("Notifications", systemImage: "bell")
                    }
                    NavigationLink { TeamView() } label: {
                        Label("Team Members", systemImage: "person.2")
                    }
                    NavigationLink { DepartmentsView() } label: {
                        Label("Departments", systemImage: "building.2")
                    }
                    NavigationLink { JobBoardView() } label: {
                        Label("Job Board", systemImage: "storefront")
                    }
                }

                // Subscription
                Section("Subscription") {
                    NavigationLink { BillingView() } label: {
                        HStack {
                            Label("Billing & Plans", systemImage: "creditcard")
                            Spacer()
                            Text("Pro")
                                .font(.system(size: 11, weight: .semibold))
                                .foregroundColor(AppTheme.primary)
                                .padding(.horizontal, 8).padding(.vertical, 3)
                                .background(AppTheme.primaryLight)
                                .cornerRadius(6)
                        }
                    }
                }

                // App
                Section("App") {
                    NavigationLink { SettingsView() } label: {
                        Label("Settings", systemImage: "gear")
                    }
                    NavigationLink { PlaceholderView(title: "Help & Support", icon: "questionmark.circle") } label: {
                        Label("Help & Support", systemImage: "questionmark.circle")
                    }
                    HStack {
                        Label("Version", systemImage: "info.circle")
                        Spacer()
                        Text("1.0.0").foregroundColor(AppTheme.textSecondary).font(.system(size: 13))
                    }
                }

                // Sign out
                Section {
                    Button(role: .destructive) {
                        authVM.signOut()
                    } label: {
                        Label("Log out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .navigationTitle("More")
            .navigationBarTitleDisplayMode(.large)
        }
    }
}

struct PlaceholderView: View {
    let title: String; let icon: String
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: icon).font(.system(size: 48)).foregroundColor(AppTheme.textTertiary)
            Text(title).font(.title2.weight(.semibold)).foregroundColor(AppTheme.textSecondary)
            Text("Coming soon").font(.subheadline).foregroundColor(AppTheme.textTertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle(title)
    }
}
