import SwiftUI
import Charts

struct AnalyticsView: View {
    @StateObject private var vm = AnalyticsViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    if vm.isLoading && vm.overview == nil {
                        ProgressView("Loading analytics…").padding(.top, 48)
                    } else if let err = vm.error {
                        ErrorBanner(message: err) { Task { await vm.load() } }
                    } else if let overview = vm.overview {
                        // Overall stats
                        HStack(spacing: 12) {
                            StatCard(icon: "person.2.fill", value: "\(overview.totalApplicants)",
                                     label: "Applicants", iconColor: AppTheme.primary)
                            StatCard(icon: "diamond.fill", value: "\(overview.totalDiamonds)",
                                     label: "Diamonds", iconColor: AppTheme.diamond)
                        }
                        .padding(.horizontal, 16)

                        HStack {
                            Text("Job Postings").font(.system(size: 16, weight: .semibold))
                            Spacer()
                            Button { vm.sortNewest.toggle() } label: {
                                HStack(spacing: 4) {
                                    Text(vm.sortNewest ? "Newest" : "Most applicants").font(.system(size: 13))
                                    Image(systemName: "chevron.down").font(.system(size: 11))
                                }
                                .foregroundColor(AppTheme.primary)
                            }
                        }
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
                .padding(.vertical, 16).padding(.bottom, 32)
            }
            .background(AppTheme.groupedBackground.ignoresSafeArea())
            .navigationTitle("Analytics")
            .navigationBarTitleDisplayMode(.large)
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
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(summary.jobTitle).font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.textPrimary).multilineTextAlignment(.leading)
                    Text(summary.department).font(.caption).foregroundColor(AppTheme.textSecondary)
                }
                Spacer()
                JobStatusTag(status: status)
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
            Text(value).font(.system(size: 20, weight: .bold)).foregroundColor(valueColor)
            Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 10)
    }
}
