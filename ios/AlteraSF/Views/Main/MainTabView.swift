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
    @State private var showCopiedToast = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                AppTopBar()
                PageHeader(title: "More", subtitle: "Account, billing, and preferences.")

                List {
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
                        NavigationLink { BillingView() } label: {
                            Label("Billing", systemImage: "creditcard")
                        }
                        NavigationLink { SettingsView() } label: {
                            Label("Settings", systemImage: "gearshape")
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
        }
    }
}
