import SwiftUI
import Charts

struct AnalyticsView: View {
    @StateObject private var vm = AnalyticsViewModel()

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                AppTopBar()
                PageHeader(title: "Analytics", subtitle: "Performance across your job postings.")
                    .background(AppTheme.pageBackground)
                ScrollView {
                  VStack(spacing: 14) {

                    if vm.isLoading && vm.overview == nil {
                        ProgressView("Loading analytics…").padding(.top, 48)
                    } else if let err = vm.error {
                        ErrorBanner(message: err) { Task { await vm.load() } }
                    } else if let overview = vm.overview {
                        // Overall stats
                        HStack(spacing: 12) {
                            StatCard(icon: "person.2", value: "\(overview.totalApplicants)",
                                     label: "Applicants", iconColor: AppTheme.primary)
                            StatCard(icon: "diamond", value: "\(overview.totalDiamonds)",
                                     label: "Diamonds", iconColor: AppTheme.diamond)
                        }
                        .padding(.horizontal, 16)

                        Text("Job Postings").font(.figtree(size: 16, weight: .semibold))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 16)

                        ForEach(vm.sortedPostings, id: \.jobCode) { summary in
                            NavigationLink {
                                JobAnalyticsView(jobCode: summary.jobCode, jobTitle: summary.jobTitle)
                            } label: {
                                AnalyticsJobCard(summary: summary)
                            }
                            .buttonStyle(.plain)
                            .padding(.horizontal, 16)
                        }
                    }
                }
                  .padding(.top, 16).padding(.bottom, 24)
                }
            }
            .background(AppTheme.groupedBackground.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .navigationBar)
            .refreshable { await vm.load() }
        }
        .task { await vm.load() }
    }
}

struct AnalyticsJobCard: View {
    let summary: APIJobAnalyticsSummary
    var status: JobStatus {
        switch summary.status.lowercased() {
        case "open": return .open
        case "closed": return .closed
        default: return .draft
        }
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(summary.jobTitle).font(.figtree(size: 17, weight: .semibold)).foregroundColor(AppTheme.textPrimary).multilineTextAlignment(.leading)
                    Text(summary.department).font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    if let posted = summary.postedDateFormatted {
                        Text("Posted \(posted)").font(.figtree(size: 11)).foregroundColor(AppTheme.textTertiary)
                    }
                }
                Spacer()
                Text(status.rawValue)
                    .font(.figtree(size: 14, weight: .medium))
                    .foregroundColor(status == .open ? .white : AppTheme.textSecondary)
                    .padding(.horizontal, 16).padding(.vertical, 8)
                    .background(status == .open ? AppTheme.primary : AppTheme.secondaryBackground)
                    .cornerRadius(8)
            }
            HStack(spacing: 0) {
                AnalyticsMetric(value: "\(summary.totalApplicants)", label: "Applicants")
                Divider().frame(height: 36)
                AnalyticsMetric(value: "\(summary.diamondsFound)", label: "Diamonds Found", valueColor: AppTheme.diamond)
            }
            .background(AppTheme.groupedBackground).cornerRadius(8)
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}

struct AnalyticsMetric: View {
    let value: String; let label: String
    var valueColor: Color = AppTheme.textPrimary
    var body: some View {
        VStack(spacing: 2) {
            Text(value).font(.figtree(size: 20, weight: .bold)).foregroundColor(valueColor)
            Text(label).font(.figtree(size: 11)).foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 10)
    }
}
