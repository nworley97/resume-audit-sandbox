import SwiftUI

struct CandidateProfileView: View {
    let candidateId: String
    let preloaded: Candidate?   // summary data passed from the list for instant display

    @State private var candidate: Candidate?
    @State private var isLoadingDetail = false
    @State private var expandedQA: Set<UUID> = []
    @State private var showArchiveAlert = false
    @State private var showFinalistToast = false

    private let api = APIService.shared

    init(candidateId: String, preloaded: Candidate? = nil) {
        self.candidateId = candidateId
        self.preloaded = preloaded
        _candidate = State(initialValue: preloaded)
    }

    var body: some View {
        ScrollView {
            if let c = candidate {
                profileContent(c)
            } else {
                ProgressView("Loading…").padding(.top, 80)
            }
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle(candidate?.fullName ?? "Candidate")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadDetail() }
        .overlay(alignment: .bottom) {
            if showFinalistToast {
                ToastView(message: "\(candidate?.firstName ?? "Candidate") added to Finalists")
                    .padding(.bottom, 24)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .onAppear {
                        Task {
                            try? await Task.sleep(nanoseconds: 2_000_000_000)
                            withAnimation { showFinalistToast = false }
                        }
                    }
            }
        }
        .animation(.easeInOut, value: showFinalistToast)
    }

    private func loadDetail() async {
        guard !isLoadingDetail else { return }
        isLoadingDetail = true
        do {
            let detail = try await api.fetchCandidate(id: candidateId)
            await MainActor.run { self.candidate = detail.toDomain() }
        } catch {
            // Keep the preloaded summary if detail fetch fails
        }
        isLoadingDetail = false
    }

    @ViewBuilder
    private func profileContent(_ c: Candidate) -> some View {
        VStack(spacing: 0) {
            // Header card
            VStack(spacing: 0) {
                HStack(alignment: .top, spacing: 16) {
                    ZStack(alignment: .topTrailing) {
                        AvatarView(initials: c.initials, size: 64)
                        if c.isDiamond {
                            Image(systemName: "diamond.fill")
                                .font(.system(size: 14)).foregroundColor(AppTheme.diamond).offset(x: 4, y: -4)
                        }
                    }
                    VStack(alignment: .leading, spacing: 4) {
                        Text(c.fullName).font(.system(size: 20, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                        if c.isDiamond {
                            HStack(spacing: 4) {
                                Image(systemName: "diamond.fill").font(.system(size: 10)).foregroundColor(AppTheme.diamond)
                                Text("Diamond in the Rough").font(.system(size: 12, weight: .medium)).foregroundColor(AppTheme.diamond)
                            }
                        }
                        if !c.phone.isEmpty {
                            Label(c.phone, systemImage: "phone").font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                        }
                        Label(c.email, systemImage: "envelope").font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                        Label("Applied \(c.appliedDate.formatted(.dateTime.month().day().year()))", systemImage: "calendar")
                            .font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                    }
                    Spacer()
                    if isLoadingDetail {
                        ProgressView().scaleEffect(0.7)
                    }
                }
                .padding(16)

                Divider()

                HStack(spacing: 0) {
                    ScoreCol(label: "Relevancy", value: c.relevancyScore)
                    Divider().frame(height: 50)
                    ScoreCol(label: "Claim Validity", value: c.claimValidityScore)
                    Divider().frame(height: 50)
                    VStack(spacing: 4) {
                        Text("\(c.tabSwitches)")
                            .font(.system(size: 22, weight: .bold))
                            .foregroundColor(c.tabSwitches > 10 ? AppTheme.danger : AppTheme.textPrimary)
                        Text("Tab Switches").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                }
                .padding(.vertical, 12)

                Divider()

                HStack(spacing: 0) {
                    Button { showArchiveAlert = true } label: {
                        VStack(spacing: 4) {
                            Image(systemName: "archivebox")
                            Text("Archive").font(.system(size: 12))
                        }
                        .foregroundColor(AppTheme.textSecondary)
                        .frame(maxWidth: .infinity).padding(.vertical, 12)
                    }
                    Divider().frame(height: 44)
                    Button {
                        showFinalistToast = true
                        api.setCandidateStatus(id: c.id, status: "finalist")
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: "star")
                            Text("Add to Finalists").font(.system(size: 12))
                        }
                        .foregroundColor(AppTheme.primary)
                        .frame(maxWidth: .infinity).padding(.vertical, 12)
                    }
                }
            }
            .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
            .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2).padding(16)

            // Resume
            if !c.education.isEmpty || !c.experience.isEmpty || !c.skills.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Resume").font(.system(size: 16, weight: .semibold))
                        Spacer()
                        if !c.resumeText.isEmpty {
                            Button { } label: {
                                Label("Download PDF", systemImage: "arrow.down.doc")
                                    .font(.system(size: 12, weight: .medium)).foregroundColor(AppTheme.primary)
                            }
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 16)

                    VStack(alignment: .leading, spacing: 12) {
                        if !c.education.isEmpty { ResumeSection(title: "Education", content: c.education) }
                        if !c.experience.isEmpty { ResumeSection(title: "Experience", content: c.experience) }
                        if !c.skills.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Skills").font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
                                FlowLayout(skills: c.skills)
                            }
                        }
                    }
                    .padding(.horizontal, 16).padding(.bottom, 16)
                }
                .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
                .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2).padding(.horizontal, 16)
            }

            // Q&A
            if !c.qaResponses.isEmpty {
                VStack(alignment: .leading, spacing: 0) {
                    HStack {
                        Text("AI Q&A Assessment").font(.system(size: 16, weight: .semibold))
                        Spacer()
                        let avg = c.qaResponses.map(\.score).reduce(0,+) / Double(c.qaResponses.count)
                        Text("\(c.qaResponses.count) questions  avg \(String(format: "%.1f", avg))/5")
                            .font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                    }
                    .padding(16)
                    Divider()
                    ForEach(Array(c.qaResponses.enumerated()), id: \.element.id) { idx, qa in
                        QAResponseRow(index: idx + 1, qa: qa, isExpanded: expandedQA.contains(qa.id)) {
                            withAnimation(.easeInOut(duration: 0.2)) {
                                if expandedQA.contains(qa.id) { expandedQA.remove(qa.id) }
                                else { expandedQA.insert(qa.id) }
                            }
                        }
                        if idx < c.qaResponses.count - 1 { Divider() }
                    }
                }
                .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
                .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2).padding(16)
            }

            Spacer(minLength: 32)
        }
        .alert("Archive candidate?", isPresented: $showArchiveAlert) {
            Button("Archive", role: .destructive) {
                api.setCandidateStatus(id: c.id, status: "archived")
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove \(c.firstName) from your active pipeline.")
        }
    }
}

// MARK: – Sub-components (unchanged)

struct ScoreCol: View {
    let label: String
    let value: Double
    var body: some View {
        VStack(spacing: 4) {
            Text(String(format: "%.1f", value)).font(.system(size: 22, weight: .bold)).foregroundColor(AppTheme.primary)
            Text("/5").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct ResumeSection: View {
    let title: String; let content: String
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
            Text(content).font(.system(size: 14)).foregroundColor(AppTheme.textPrimary)
        }
    }
}

struct FlowLayout: View {
    let skills: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 80), spacing: 6)], spacing: 6) {
            ForEach(skills, id: \.self) { skill in TagView(text: skill, color: AppTheme.primary) }
        }
    }
}

struct QAResponseRow: View {
    let index: Int; let qa: QAResponse; let isExpanded: Bool; let onToggle: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button(action: onToggle) {
                HStack(alignment: .top, spacing: 12) {
                    Text("Q\(index) \(qa.question)").font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary).multilineTextAlignment(.leading)
                    Spacer()
                    VStack(alignment: .trailing, spacing: 4) {
                        HStack(spacing: 4) {
                            Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.primary).font(.system(size: 12))
                            Text(String(format: "%.1f/5", qa.score)).font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                        }
                        Label(qa.durationFormatted, systemImage: "clock").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                    }
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down").font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                }
                .padding(16)
            }
            .buttonStyle(.plain)
            if isExpanded {
                VStack(alignment: .leading, spacing: 8) {
                    Text(qa.answer).font(.system(size: 14)).foregroundColor(AppTheme.textPrimary)
                    if qa.hasPastedContent {
                        HStack(spacing: 4) {
                            Image(systemName: "doc.on.clipboard").font(.system(size: 11))
                            Text("Highlighted text indicates content the candidate pasted into their answer.").font(.system(size: 11))
                        }
                        .foregroundColor(AppTheme.warning).padding(8)
                        .background(AppTheme.warning.opacity(0.1)).cornerRadius(6)
                    }
                }
                .padding(.horizontal, 16).padding(.bottom, 16)
            }
        }
    }
}

private extension APIService {
    func setCandidateStatus(id: String, status: String) {
        Task { try? await self.setCandidateStatus(id: id, status: status) }
    }
}
