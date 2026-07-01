import SwiftUI

@MainActor
final class JobBoardViewModel: ObservableObject {
    @Published var openJobs: [Job] = []
    @Published var isLoading = false
    @Published var error: String? = nil
    private let api = APIService.shared

    func load() async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let apiJobs = try await api.fetchJobs(status: "open")
            openJobs = apiJobs.map { $0.toDomain() }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct JobBoardView: View {
    @StateObject private var vm = JobBoardViewModel()
    @State private var showCopiedToast = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 0) {
                    // Public header banner
                    VStack(spacing: 8) {
                        Text("Join Our Team")
                            .font(.system(size: 24, weight: .bold))
                            .foregroundColor(.white)
                        Text("Help us build the future of fair, AI-assisted hiring. We're growing across engineering, design, and sales.")
                            .font(.subheadline)
                            .foregroundColor(.white.opacity(0.85))
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 24)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 32)
                    .background(
                        LinearGradient(
                            colors: [AppTheme.primary, AppTheme.primaryDark],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )

                    // Position count
                    HStack {
                        Text("Open Positions")
                            .font(.system(size: 16, weight: .semibold))
                        Spacer()
                        if vm.isLoading {
                            ProgressView().scaleEffect(0.7)
                        } else {
                            Text("\(vm.openJobs.count) positions available")
                                .font(.system(size: 13))
                                .foregroundColor(AppTheme.textSecondary)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)

                    Divider()

                    if let err = vm.error {
                        ErrorBanner(message: err) { Task { await vm.load() } }
                            .padding(16)
                    } else {
                        LazyVStack(spacing: 0) {
                            ForEach(vm.openJobs) { job in
                                PublicJobCard(job: job)
                                Divider()
                            }
                        }
                    }
                }
            }
            .background(AppTheme.background.ignoresSafeArea())
            .navigationTitle("Job Board")
            .navigationBarTitleDisplayMode(.inline)
            .refreshable { await vm.load() }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        UIPasteboard.general.string = "https://jobs.alterasf.com"
                        showCopiedToast = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            showCopiedToast = false
                        }
                    } label: {
                        Label("Copy link", systemImage: "link")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(AppTheme.primary)
                    }
                }
            }
            .overlay(alignment: .bottom) {
                if showCopiedToast {
                    ToastView(message: "Job board link copied")
                        .padding(.bottom, 24)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.easeInOut, value: showCopiedToast)

            // Powered by footer
            VStack(spacing: 4) {
                Divider()
                HStack(spacing: 4) {
                    Image(systemName: "bolt.fill")
                        .font(.system(size: 11))
                        .foregroundColor(AppTheme.primary)
                    Text("Powered by AlteraSF")
                        .font(.system(size: 12))
                        .foregroundColor(AppTheme.textSecondary)
                }
                .padding(.vertical, 8)
            }
            .background(AppTheme.background)
        }
        .task { await vm.load() }
    }
}

struct PublicJobCard: View {
    let job: Job
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Now Hiring")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(AppTheme.primary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(AppTheme.primaryLight)
                    .cornerRadius(4)
                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)

            VStack(alignment: .leading, spacing: 6) {
                Text(job.title)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)

                HStack(spacing: 12) {
                    Label(job.workArrangement.rawValue, systemImage: "location")
                        .font(.system(size: 12))
                    Label(job.employmentType.rawValue, systemImage: "briefcase")
                        .font(.system(size: 12))
                }
                .foregroundColor(AppTheme.textSecondary)

                if job.salaryMin > 0 {
                    Label("$\(job.salaryMin / 1000)K – $\(job.salaryMax / 1000)K", systemImage: "dollarsign.circle")
                        .font(.system(size: 12))
                        .foregroundColor(AppTheme.textSecondary)
                }

                Text(job.description)
                    .font(.system(size: 14))
                    .foregroundColor(AppTheme.textSecondary)
                    .lineLimit(expanded ? nil : 2)

                HStack {
                    Button {
                        withAnimation { expanded.toggle() }
                    } label: {
                        Text(expanded ? "Show less" : "Read more")
                            .font(.system(size: 13))
                            .foregroundColor(AppTheme.primary)
                    }
                    Spacer()
                    Button {
                    } label: {
                        HStack(spacing: 4) {
                            Text("Apply Now")
                                .font(.system(size: 14, weight: .semibold))
                            Image(systemName: "arrow.right")
                                .font(.system(size: 13))
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 8)
                        .background(AppTheme.primary)
                        .cornerRadius(8)
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .padding(.bottom, 4)
        }
    }
}
