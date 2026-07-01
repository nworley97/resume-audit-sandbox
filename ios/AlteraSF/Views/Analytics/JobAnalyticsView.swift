import SwiftUI
import Charts

struct JobAnalyticsView: View {
    let jobCode: String
    let jobTitle: String

    @StateObject private var vm = JobAnalyticsViewModel()

    var body: some View {
        ScrollView {
            if vm.isLoading && vm.detail == nil {
                ProgressView("Loading analytics…").padding(.top, 80)
            } else if let err = vm.error {
                ErrorBanner(message: err) { Task { await vm.load(code: jobCode) } }
            } else if let d = vm.detail {
                VStack(spacing: 16) {
                    // Hero stats
                    HStack(spacing: 12) {
                        StatCard(icon: "person.2", value: "\(d.totalApplicants)", label: "Total Applications", iconColor: AppTheme.primary)
                        StatCard(icon: "diamond.fill", value: "\(d.diamondsFound)", label: "Diamonds Found", iconColor: AppTheme.diamond)
                    }
                    HStack(spacing: 12) {
                        StatCard(icon: "checkmark.circle", value: "\(String(format: "%.1f", d.completionRate))%", label: "Completion Rate", iconColor: AppTheme.success)
                        StatCard(icon: "clock", value: "\(String(format: "%.1fh", d.timeSavedHours))", label: "Time Saved", iconColor: AppTheme.warning)
                    }

                    // Diamonds leaderboard
                    if !d.diamonds.isEmpty {
                        DiamondLeaderboard(candidates: d.diamonds.map { $0.toDomain() })
                    }

                    // Score distributions
                    if !d.claimScoreDistribution.isEmpty {
                        ScoreDistributionCard(
                            claimData: d.claimScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) },
                            fitData: d.fitScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) }
                        )
                    }

                    // Funnel
                    FunnelCard(funnel: FunnelData(
                        applied: d.funnel.applied, started: d.funnel.started,
                        completed: d.funnel.completed, verified: d.funnel.verified, passed: d.funnel.passed
                    ))

                    // ROI
                    ROICard(timeSaved: d.timeSavedHours, screenSpeed: d.screenSpeed, reviewLoad: d.reviewLoadReduction)
                }
                .padding(.top, 16).padding(.bottom, 32).padding(.horizontal, 16)
            }
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle(jobTitle)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    UIPasteboard.general.string = "https://jobs.alterasf.com/\(jobCode)"
                } label: { Image(systemName: "square.and.arrow.up") }
                .foregroundColor(AppTheme.textPrimary)
            }
        }
        .task { await vm.load(code: jobCode) }
        .refreshable { await vm.load(code: jobCode) }
    }
}

struct DiamondLeaderboard: View {
    let candidates: [Candidate]
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "diamond.fill").foregroundColor(AppTheme.diamond)
                Text("Diamonds in the Rough").font(.system(size: 16, weight: .semibold))
            }
            Text("Top performers worth a closer look.").font(.caption).foregroundColor(AppTheme.textSecondary)
            ForEach(Array(candidates.prefix(4).enumerated()), id: \.element.id) { idx, c in
                NavigationLink {
                    CandidateProfileView(candidateId: c.id, preloaded: c)
                } label: {
                    HStack(spacing: 12) {
                        Text("\(idx + 1)").font(.system(size: 13, weight: .bold)).foregroundColor(AppTheme.textSecondary).frame(width: 20)
                        AvatarView(initials: c.initials, size: 36)
                        Text(c.fullName).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(String(format: "%.1f", c.claimValidityScore)).font(.system(size: 13, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                            Text("Claim \(String(format: "%.1f", c.relevancyScore))").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                        }
                        Image(systemName: "chevron.right").font(.caption).foregroundColor(AppTheme.textTertiary)
                    }
                    .padding(.vertical, 6)
                }
                .buttonStyle(.plain)
                if idx < min(candidates.count, 4) - 1 { Divider() }
            }
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}

struct ScoreDistributionCard: View {
    let claimData: [ScoreBucket]
    let fitData: [ScoreBucket]
    @State private var showClaim = true
    var currentData: [ScoreBucket] { showClaim ? claimData : fitData }
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Score Distribution").font(.system(size: 16, weight: .semibold))
            Picker("", selection: $showClaim) {
                Text("Claim Validity").tag(true)
                Text("Job Fit").tag(false)
            }
            .pickerStyle(.segmented)
            Chart(currentData) { bucket in
                BarMark(x: .value("Score", bucket.label), y: .value("Count", bucket.count))
                    .foregroundStyle(AppTheme.primary.gradient).cornerRadius(4)
            }
            .frame(height: 140)
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}

struct FunnelCard: View {
    let funnel: FunnelData
    private var steps: [(label: String, count: Int, color: Color)] {[
        ("Applied", funnel.applied, AppTheme.primary),
        ("Started", funnel.started, AppTheme.primary.opacity(0.8)),
        ("Completed", funnel.completed, AppTheme.primary.opacity(0.65)),
        ("Verified", funnel.verified, AppTheme.primary.opacity(0.5)),
        ("Passed", funnel.passed, AppTheme.success),
    ]}
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Verification Funnel").font(.system(size: 16, weight: .semibold))
            Text("From application to verified pass.").font(.caption).foregroundColor(AppTheme.textSecondary)
            Chart(steps.indices, id: \.self) { idx in
                BarMark(x: .value("Stage", steps[idx].label), y: .value("Count", steps[idx].count))
                    .foregroundStyle(steps[idx].color.gradient).cornerRadius(6)
            }
            .frame(height: 160)
            HStack(spacing: 0) {
                ForEach(steps.indices, id: \.self) { idx in
                    VStack(spacing: 2) {
                        Text("\(steps[idx].count)").font(.system(size: 14, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                        Text(steps[idx].label).font(.system(size: 9)).foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                    if idx < steps.count - 1 { Image(systemName: "chevron.right").font(.system(size: 9)).foregroundColor(AppTheme.textTertiary) }
                }
            }
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}

struct ROICard: View {
    let timeSaved: Double; let screenSpeed: Double; let reviewLoad: Double
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("ROI Impact").font(.system(size: 16, weight: .semibold))
            HStack(spacing: 12) {
                ROIMetric(label: "Time Saved", value: String(format: "%.1fh", timeSaved), icon: "clock.fill")
                ROIMetric(label: "Screen Speed", value: "\(Int(screenSpeed))%", icon: "bolt.fill")
                ROIMetric(label: "Review Load↓", value: "\(Int(reviewLoad))%", icon: "arrow.down.circle.fill")
            }
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}

struct ROIMetric: View {
    let label: String; let value: String; let icon: String
    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon).font(.system(size: 20)).foregroundColor(AppTheme.primary)
            Text(value).font(.system(size: 17, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text(label).font(.system(size: 10)).foregroundColor(AppTheme.textSecondary).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity).padding(.vertical, 12)
        .background(AppTheme.groupedBackground).cornerRadius(10)
    }
}
