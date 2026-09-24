import SwiftUI
import Charts

struct JobAnalyticsView: View {
    let jobCode: String
    let jobTitle: String

    @StateObject private var vm = JobAnalyticsViewModel()
    @State private var navigateToCandidates = false

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

                    Button { navigateToCandidates = true } label: {
                        HStack(spacing: 10) {
                            Image(systemName: "person.3.fill").foregroundColor(AppTheme.primary)
                            Text("View All Candidates").font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                            Spacer()
                            Image(systemName: "chevron.right").font(.caption).foregroundColor(AppTheme.textTertiary)
                        }
                        .padding(14)
                        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
                        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
                    }
                    .buttonStyle(.plain)

                    // Diamonds leaderboard
                    if !d.diamonds.isEmpty {
                        DiamondLeaderboard(candidates: d.diamonds.map { $0.toDomain() })
                    }

                    // Added finalists
                    FinalistsCard(vm: vm, jobCode: jobCode)

                    // Score distributions
                    if !d.claimScoreDistribution.isEmpty {
                        ScoreDistributionCard(
                            claimData: d.claimScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) },
                            fitData: d.fitScoreDistribution.map { ScoreBucket(label: $0.label, count: $0.count, score: $0.score) }
                        )
                    }

                    // Cross Validation Matrix
                    CrossValidationMatrixCard(heatmap: d.heatmap)

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
        .navigationDestination(isPresented: $navigateToCandidates) {
            CandidatesView(filterJobId: jobCode, filterJobTitle: jobTitle)
        }
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

struct CrossValidationMatrixCard: View {
    let heatmap: APIAnalyticsHeatmap
    @State private var selectedCell: APIHeatmapCell?

    // Web parity: the "No Score" relevancy row is excluded from the grid.
    private var relevancyRows: [APIHeatmapRelevancyAxisEntry] {
        heatmap.axes.relevancy.filter { !$0.isNoScore }
    }
    private var claimColumns: [APIHeatmapClaimAxisEntry] { heatmap.axes.claimValidity }

    private func cell(relevancy: Int, claim: Int) -> APIHeatmapCell? {
        heatmap.cells.first { $0.relevancy == relevancy && $0.claim == claim }
    }

    private func tone(relevancy: APIHeatmapRelevancyAxisEntry, claim: APIHeatmapClaimAxisEntry, count: Int) -> Color {
        guard count > 0 else { return AppTheme.groupedBackground }
        let rel = relevancy.value ?? 0
        let claimBucket = claim.bucket
        if rel == 5 && claimBucket == 5 { return AppTheme.diamond }
        if (rel == 4 && claimBucket >= 4) || (rel == 5 && claimBucket == 4) { return AppTheme.success }
        if rel >= 3 && claimBucket >= 3 { return AppTheme.warning }
        return AppTheme.danger.opacity(0.6)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Cross Validation Matrix").font(.system(size: 16, weight: .semibold))
            Text("Fit score vs. claim validity across all applicants.").font(.caption).foregroundColor(AppTheme.textSecondary)

            ScrollView(.horizontal, showsIndicators: false) {
                Grid(horizontalSpacing: 4, verticalSpacing: 4) {
                    GridRow {
                        Color.clear.frame(width: 44, height: 28)
                        ForEach(claimColumns, id: \.index) { col in
                            Text(col.label).font(.system(size: 9, weight: .medium)).foregroundColor(AppTheme.textSecondary)
                                .frame(width: 44, height: 28)
                        }
                    }
                    ForEach(relevancyRows, id: \.index) { row in
                        GridRow {
                            Text(row.label).font(.system(size: 9, weight: .medium)).foregroundColor(AppTheme.textSecondary)
                                .frame(width: 44, height: 40)
                            ForEach(claimColumns, id: \.index) { col in
                                let matchedCell = cell(relevancy: row.index, claim: col.index)
                                let count = matchedCell?.candidates.count ?? 0
                                Button {
                                    if count > 0 { selectedCell = matchedCell }
                                } label: {
                                    Text(count > 0 ? "\(count)" : "").font(.system(size: 12, weight: .bold)).foregroundColor(.white)
                                        .frame(width: 44, height: 40)
                                        .background(tone(relevancy: row, claim: col, count: count))
                                        .cornerRadius(6)
                                }
                                .buttonStyle(.plain)
                                .disabled(count == 0)
                            }
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
        .sheet(item: $selectedCell) { cell in
            NavigationStack {
                List(cell.candidates, id: \.id) { c in
                    NavigationLink {
                        CandidateProfileView(candidateId: c.id)
                    } label: {
                        HStack(spacing: 12) {
                            AvatarView(initials: c.initials, size: 36)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(c.name).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                                Text("Fit \(String(format: "%.1f", c.relevancyScore)) · Claim \(c.claimValidityScore.map { String(format: "%.1f", $0) } ?? "—")")
                                    .font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                            }
                        }
                    }
                }
                .navigationTitle("Candidates")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) {
                        Button("Close") { selectedCell = nil }
                    }
                }
            }
        }
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

struct FinalistsCard: View {
    @EnvironmentObject var authVM: AuthViewModel
    @ObservedObject var vm: JobAnalyticsViewModel
    let jobCode: String

    @State private var showAll = false
    @State private var showAddSheet = false
    @State private var noteDraftFor: APIFinalist? = nil
    @State private var noteDraftText = ""

    private var finalists: [APIFinalist] { vm.detail?.finalists ?? [] }
    private var visible: [APIFinalist] { showAll ? finalists : Array(finalists.prefix(5)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Added Finalists").font(.system(size: 16, weight: .semibold))
                    Text("Shortlisted candidates you're comparing for this role.")
                        .font(.caption).foregroundColor(AppTheme.textSecondary)
                }
                Spacer()
                if authVM.canManageHiring {
                Button { showAddSheet = true } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "plus")
                        Text("Add")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.white)
                    .padding(.horizontal, 12).padding(.vertical, 7)
                    .background(AppTheme.primary).cornerRadius(8)
                }
                .buttonStyle(.plain)
                }
            }

            if finalists.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "star").font(.system(size: 28)).foregroundColor(AppTheme.textTertiary)
                    Text("No finalists added yet. Use \u{201C}Add\u{201D} to build your shortlist.")
                        .font(.caption).foregroundColor(AppTheme.textSecondary)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity).padding(.vertical, 20)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(visible.enumerated()), id: \.element.id) { idx, f in
                        FinalistRow(
                            finalist: f,
                            canManage: authVM.canManageHiring,
                            onRemove: { Task { await vm.removeFinalist(candidateId: f.id, jobCode: jobCode) } },
                            onEditNote: { noteDraftFor = f; noteDraftText = f.note }
                        )
                        if idx < visible.count - 1 { Divider() }
                    }
                }
                if finalists.count > 5 {
                    Button(showAll ? "Show less" : "View all (\(finalists.count))") {
                        showAll.toggle()
                    }
                    .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
                }
            }
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
        .sheet(isPresented: $showAddSheet) {
            AddFinalistsSheet(vm: vm, jobCode: jobCode)
        }
        .sheet(item: $noteDraftFor) { finalist in
            NoteEditorSheet(finalist: finalist, draft: $noteDraftText) { text in
                Task { await vm.updateNote(candidateId: finalist.id, note: text, jobCode: jobCode) }
            }
        }
    }
}

struct FinalistRow: View {
    let finalist: APIFinalist
    let canManage: Bool
    let onRemove: () -> Void
    let onEditNote: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                AvatarView(initials: finalist.initials, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(finalist.name).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                        if finalist.flagged {
                            HStack(spacing: 2) {
                                Image(systemName: "exclamationmark.triangle.fill").font(.system(size: 9))
                                Text("Flagged").font(.system(size: 10, weight: .semibold))
                            }
                            .foregroundColor(AppTheme.danger)
                            .padding(.horizontal, 6).padding(.vertical, 2)
                            .background(AppTheme.danger.opacity(0.12)).cornerRadius(4)
                        }
                    }
                    if finalist.flagged, let reason = finalist.flagReason {
                        Text(reason).font(.system(size: 10)).foregroundColor(AppTheme.danger.opacity(0.8))
                    }
                }
                Spacer()
                VStack(alignment: .trailing, spacing: 2) {
                    Text(String(format: "%.1f", finalist.overallScore)).font(.system(size: 14, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                    Text("Overall").font(.system(size: 9)).foregroundColor(AppTheme.textSecondary)
                }
                if canManage {
                    Button(action: onRemove) {
                        Image(systemName: "xmark.circle.fill").foregroundColor(AppTheme.textTertiary)
                    }
                    .buttonStyle(.plain)
                }
            }

            HStack(spacing: 16) {
                finalistMetric("Relevancy", String(format: "%.1f", finalist.relevancyScore))
                finalistMetric("Claim", String(format: "%.1f", finalist.claimValidityScore))
                finalistMetric("AI/QA", finalist.totalAnswers > 0 ? "\(finalist.flaggedAnswers)/\(finalist.totalAnswers)" : "\u{2014}")
                finalistMetric("Tabs", "\(finalist.tabSwitches)")
                Spacer()
                if canManage {
                    Button(finalist.note.isEmpty ? "+ Note" : "Edit Note", action: onEditNote)
                        .font(.system(size: 11, weight: .medium)).foregroundColor(AppTheme.primary)
                } else if !finalist.note.isEmpty {
                    Text(finalist.note).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                }
            }
        }
        .padding(.vertical, 10)
    }

    private func finalistMetric(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(value).font(.system(size: 12, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
            Text(label).font(.system(size: 9)).foregroundColor(AppTheme.textSecondary)
        }
    }
}

struct AddFinalistsSheet: View {
    @ObservedObject var vm: JobAnalyticsViewModel
    let jobCode: String
    @Environment(\.dismiss) var dismiss
    @State private var search = ""
    @State private var options: [APIFinalistCandidateOption] = []
    @State private var isLoading = false
    @State private var addingId: String?

    private var filtered: [APIFinalistCandidateOption] {
        search.isEmpty ? options : options.filter { $0.name.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Add finalists").font(.system(size: 20, weight: .bold))
            Text("Shortlisted candidates you're comparing for this role.")
                .font(.system(size: 14)).foregroundColor(AppTheme.textSecondary)
            if options.count > 6 {
                TextField("Search candidates…", text: $search)
                    .textFieldStyle(AlteraTextFieldStyle())
            }
            if let error = vm.error { Text(error).font(.caption).foregroundColor(AppTheme.danger) }
            ScrollView {
                if isLoading {
                    ProgressView().padding(24)
                } else if filtered.isEmpty {
                    Text("No remaining candidates to add.")
                        .font(.subheadline).foregroundColor(AppTheme.textSecondary).padding(.vertical, 24)
                } else {
                    VStack(spacing: 0) {
                        ForEach(filtered) { candidate in candidateRow(candidate) }
                    }
                }
            }
            Button("Done") { dismiss() }.buttonStyle(AlteraButtonStyle())
        }
        .padding(24)
        .presentationDetents([.height(520), .large])
        .presentationDragIndicator(.visible)
        .task {
            isLoading = true
            options = await vm.loadCandidateOptions(jobCode: jobCode)
            isLoading = false
        }
    }

    private func candidateRow(_ candidate: APIFinalistCandidateOption) -> some View {
        HStack(spacing: 12) {
            AvatarView(initials: candidate.name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined(), size: 36)
            VStack(alignment: .leading, spacing: 2) {
                Text(candidate.name).font(.system(size: 15, weight: .medium))
                Text("Fit \(String(format: "%.1f", candidate.relevancyScore))")
                    .font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
            }
            Spacer()
            Button {
                addingId = candidate.id
                vm.error = nil
                Task {
                    await vm.addFinalist(candidateId: candidate.id, jobCode: jobCode)
                    if vm.error == nil { options.removeAll { $0.id == candidate.id } }
                    addingId = nil
                }
            } label: {
                Group {
                    if addingId == candidate.id { ProgressView() }
                    else { Image(systemName: "plus.circle").font(.system(size: 20)) }
                }
                .frame(width: 44, height: 44)
            }
            .foregroundColor(AppTheme.primary)
            .disabled(addingId != nil)
            .accessibilityLabel("Add \(candidate.name) to finalists")
        }
        .padding(.vertical, 8)
    }
}

struct NoteEditorSheet: View {
    let finalist: APIFinalist
    @Binding var draft: String
    let onSave: (String) -> Void
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Note").font(.system(size: 20, weight: .bold))
            Text("Private to your team.").font(.system(size: 14)).foregroundColor(AppTheme.textSecondary)
            TextEditor(text: $draft)
                .font(.system(size: 15))
                .scrollContentBackground(.hidden)
                .padding(10)
                .frame(minHeight: 140, maxHeight: 200)
                .background(AppTheme.groupedBackground)
                .clipShape(RoundedRectangle(cornerRadius: AppTheme.cornerRadius))
                .accessibilityLabel("Note about \(finalist.name)")
            HStack(spacing: 12) {
                Button("Cancel") { dismiss() }.buttonStyle(AlteraButtonStyle(secondary: true))
                Button("Save") {
                    onSave(draft.trimmingCharacters(in: .whitespacesAndNewlines))
                    dismiss()
                }.buttonStyle(AlteraButtonStyle())
            }
        }
        .padding(24)
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}
