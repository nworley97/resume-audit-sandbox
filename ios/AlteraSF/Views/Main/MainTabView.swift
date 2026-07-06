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

            MoreView()
                .tabItem { Label("More", systemImage: "ellipsis") }
                .tag(3)
        }
        .tint(AppTheme.primary)
    }
}

struct MoreView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @State private var planDisplay: String? = nil

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
                }

                // Subscription
                Section("Subscription") {
                    NavigationLink { BillingView() } label: {
                        HStack {
                            Label("Billing & Plans", systemImage: "creditcard")
                            Spacer()
                            if let planDisplay {
                                Text(planDisplay)
                                    .font(.system(size: 11, weight: .semibold))
                                    .foregroundColor(AppTheme.primary)
                                    .padding(.horizontal, 8).padding(.vertical, 3)
                                    .background(AppTheme.primaryLight)
                                    .cornerRadius(6)
                            }
                        }
                    }
                }

                // App
                Section("App") {
                    NavigationLink { SettingsView() } label: {
                        Label("Settings", systemImage: "gear")
                    }
                    NavigationLink { HelpSupportView() } label: {
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
            .task {
                planDisplay = try? await APIService.shared.fetchBilling().summary.planDisplay
            }
        }
    }
}
