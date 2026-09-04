import SwiftUI

struct CandidateProfileView: View {
    @EnvironmentObject var authVM: AuthViewModel
    let candidateId: String
    let preloaded: Candidate?   // summary data passed from the list for instant display

    @State private var candidate: Candidate?
    @State private var isLoadingDetail = false
    @State private var expandedQA: Set<UUID> = []
    @State private var showArchiveAlert = false
    @State private var showFinalistToast = false
    @State private var isDownloadingResume = false
    @State private var resumeShareURL: URL?
    @State private var resumeDownloadError: String?

    private let api = APIService.shared

    init(candidateId: String, preloaded: Candidate? = nil) {
        self.candidateId = candidateId
        self.preloaded = preloaded
        _candidate = State(initialValue: preloaded)
    }

    var body: some View {
        ZStack(alignment: .bottom) {
            ScrollView {
                if let c = candidate {
                    profileContent(c)
                        .padding(.bottom, 84)
                } else {
                    ProgressView("Loading…").padding(.top, 80)
                }
            }
            if let c = candidate, authVM.canManageHiring {
                bottomActionBar(c)
            }
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle(candidate?.fullName ?? "Candidate")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    if let c = candidate {
                        Button {
                            UIPasteboard.general.string = c.email
                        } label: { Label("Copy email", systemImage: "doc.on.doc") }
                        if !c.resumeUrl.isEmpty {
                            Button {
                                Task { await downloadResume(candidateId: c.id) }
                            } label: { Label("Download résumé", systemImage: "arrow.down.doc") }
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle").foregroundColor(AppTheme.textPrimary)
                }
            }
        }
        .task { await loadDetail() }
        .overlay(alignment: .bottom) {
            if showFinalistToast {
                ToastView(message: "\(candidate?.firstName ?? "Candidate") added to Finalists")
                    .padding(.bottom, 96)
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
        .sheet(item: Binding(
            get: { resumeShareURL.map { IdentifiableURL(url: $0) } },
            set: { resumeShareURL = $0?.url }
        )) { wrapped in
            ShareSheet(items: [wrapped.url])
        }
        .alert("Couldn't download resume", isPresented: Binding(
            get: { resumeDownloadError != nil },
            set: { if !$0 { resumeDownloadError = nil } }
        )) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(resumeDownloadError ?? "")
        }
        .alert("Archive candidate?", isPresented: $showArchiveAlert) {
            Button("Archive", role: .destructive) {
                api.setCandidateStatus(id: candidate?.id ?? candidateId, status: "archived")
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove \(candidate?.firstName ?? "this candidate") from your active pipeline.")
        }
    }

    @ViewBuilder
    private func bottomActionBar(_ c: Candidate) -> some View {
        HStack(spacing: 12) {
            Button { showArchiveAlert = true } label: {
                Label("Archive", systemImage: "archivebox")
                    .font(.system(size: 15, weight: .medium))
                    .frame(maxWidth: .infinity).frame(height: 48)
            }
            .background(AppTheme.secondaryBackground)
            .foregroundColor(AppTheme.textPrimary)
            .cornerRadius(AppTheme.buttonCornerRadius)

            Button {
                showFinalistToast = true
                api.setCandidateStatus(id: c.id, status: "finalist")
            } label: {
                Label("Add to Finalists", systemImage: "star.fill")
                    .font(.system(size: 15, weight: .semibold))
                    .frame(maxWidth: .infinity).frame(height: 48)
            }
            .background(AppTheme.primary)
            .foregroundColor(.white)
            .cornerRadius(AppTheme.buttonCornerRadius)
        }
        .padding(.horizontal, 16).padding(.vertical, 12)
        .background(.regularMaterial)
    }

    private func downloadResume(candidateId: String) async {
        guard !isDownloadingResume else { return }
        isDownloadingResume = true
        defer { isDownloadingResume = false }
        do {
            let (data, filename) = try await api.fetchResumeData(candidateId: candidateId)
            let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent(filename)
            try data.write(to: tempURL, options: .atomic)
            resumeShareURL = tempURL
        } catch {
            resumeDownloadError = error.localizedDescription
        }
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
                    VStack(alignment: .leading, spacing: 6) {
                        Text(c.fullName).font(.system(size: 20, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                        if c.isDiamond {
                            HStack(spacing: 4) {
                                Image(systemName: "diamond.fill").font(.system(size: 9)).foregroundColor(AppTheme.diamond)
                                Text("Diamond in the Rough").font(.system(size: 11, weight: .semibold)).foregroundColor(AppTheme.diamond)
                            }
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(AppTheme.primaryLight)
                            .cornerRadius(20)
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
            }
            .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
            .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2).padding(16)

            // Stat cards
            HStack(spacing: 10) {
                ProfileScoreCard(label: "Relevancy", value: c.relevancyScore)
                ProfileScoreCard(label: "Claim Validity", value: c.claimValidityScore)
                ProfileTabSwitchCard(value: c.tabSwitches)
            }
            .padding(.horizontal, 16).padding(.bottom, 16)

            // Resume
            if !c.education.isEmpty || !c.experience.isEmpty || !c.skills.isEmpty || !c.resumeUrl.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    HStack(alignment: .top) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Résumé").font(.system(size: 16, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
                            Text("AI cross-checked against answers").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, 16).padding(.top, 16)

                    if !c.resumeUrl.isEmpty {
                        Button {
                            Task { await downloadResume(candidateId: c.id) }
                        } label: {
                            HStack {
                                if isDownloadingResume {
                                    ProgressView().scaleEffect(0.8)
                                } else {
                                    Image(systemName: "arrow.down.doc")
                                    Text("Download Résumé PDF").font(.system(size: 14, weight: .medium))
                                }
                            }
                            .frame(maxWidth: .infinity).frame(height: 44)
                        }
                        .disabled(isDownloadingResume)
                        .foregroundColor(AppTheme.textPrimary)
                        .background(AppTheme.secondaryBackground)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                        .padding(.horizontal, 16)
                    }

                    ResumeDocumentCard(candidate: c)
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
    }
}

// MARK: – Sub-components

struct ProfileScoreCard: View {
    let label: String
    let value: Double
    private var tint: Color {
        value >= 4 ? AppTheme.success : (value >= 3 ? AppTheme.warning : AppTheme.danger)
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            Text(String(format: "%.1f/5", value))
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(tint)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(tint.opacity(0.15))
                .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.background)
        .cornerRadius(AppTheme.cornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 6, x: 0, y: 2)
    }
}

struct ProfileTabSwitchCard: View {
    let value: Int
    private var tint: Color { value > 10 ? AppTheme.danger : AppTheme.warning }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Tab Switches").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            Text("\(value)")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(tint)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(tint.opacity(0.15))
                .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(AppTheme.background)
        .cornerRadius(AppTheme.cornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 6, x: 0, y: 2)
    }
}

struct ResumeDocumentCard: View {
    let candidate: Candidate

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            // Name + contact header
            VStack(alignment: .leading, spacing: 4) {
                Text(candidate.fullName)
                    .font(.system(size: 19, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)
                Text([candidate.phone, candidate.email, candidate.location].filter { !$0.isEmpty }.joined(separator: "   ·   "))
                    .font(.system(size: 12))
                    .foregroundColor(AppTheme.textSecondary)
            }
            .padding(.bottom, 12)
            .overlay(Rectangle().frame(height: 1).foregroundColor(AppTheme.divider), alignment: .bottom)

            if !candidate.education.isEmpty {
                ResumeSection(title: "Education") {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(parseResumeEntries(candidate.education)) { entry in
                            ResumeEntryView(entry: entry)
                        }
                    }
                }
            }

            if !candidate.skills.isEmpty {
                ResumeSection(title: "Skills") {
                    FlowLayout(skills: candidate.skills)
                }
            }

            if !candidate.experience.isEmpty {
                ResumeSection(title: "Experience") {
                    VStack(alignment: .leading, spacing: 14) {
                        ForEach(parseResumeEntries(candidate.experience)) { entry in
                            ResumeEntryView(entry: entry)
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(AppTheme.groupedBackground)
        .cornerRadius(AppTheme.cornerRadius)
        .overlay(
            RoundedRectangle(cornerRadius: AppTheme.cornerRadius)
                .stroke(AppTheme.divider, lineWidth: 1)
        )
    }
}

struct ResumeSection<Content: View>: View {
    let title: String
    @ViewBuilder let content: Content
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .bold))
                .tracking(1.2)
                .foregroundColor(AppTheme.primary)
                .padding(.bottom, 5)
                .overlay(Rectangle().frame(height: 1).foregroundColor(AppTheme.divider), alignment: .bottom)
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// A single résumé entry (one education or experience item), parsed from either the
/// backend's multi-line "title\nsubtitle\nLabel: value" format or the single-line
/// "Institution — Degree, detail" / "Title, Company (Dates)" mock format.
struct ResumeEntry: Identifiable {
    let id = UUID()
    let header: String
    let trailing: String
    let subheader: String
    let details: [String]
}

struct ResumeEntryView: View {
    let entry: ResumeEntry
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(entry.header).font(.system(size: 14, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                Spacer()
                if !entry.trailing.isEmpty {
                    Text(entry.trailing).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                }
            }
            if !entry.subheader.isEmpty {
                Text(entry.subheader).font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.primary)
            }
            ForEach(entry.details, id: \.self) { line in
                if line.contains(": ") {
                    Text(line).font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                } else {
                    HStack(alignment: .top, spacing: 6) {
                        Text("•").font(.system(size: 13)).foregroundColor(AppTheme.primary)
                        Text(line).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private func parseResumeEntries(_ text: String) -> [ResumeEntry] {
    text.components(separatedBy: "\n\n").compactMap { block in
        var lines = block.components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        guard !lines.isEmpty else { return nil }

        var header = lines.removeFirst()
        var trailing = ""
        if let openParen = header.lastIndex(of: "("), let closeParen = header.lastIndex(of: ")"), openParen < closeParen {
            trailing = String(header[header.index(after: openParen)..<closeParen]).trimmingCharacters(in: .whitespaces)
            header = String(header[..<openParen]).trimmingCharacters(in: .whitespaces)
        }

        var subheader = ""
        if let dashRange = header.range(of: "—") {
            subheader = String(header[dashRange.upperBound...]).trimmingCharacters(in: .whitespaces)
            header = String(header[..<dashRange.lowerBound]).trimmingCharacters(in: .whitespaces)
        } else if !trailing.isEmpty, let commaIdx = header.firstIndex(of: ",") {
            subheader = String(header[header.index(after: commaIdx)...]).trimmingCharacters(in: .whitespaces)
            header = String(header[..<commaIdx]).trimmingCharacters(in: .whitespaces)
        } else if let first = lines.first, !first.contains(": ") {
            subheader = first
            lines.removeFirst()
        }

        return ResumeEntry(header: header, trailing: trailing, subheader: subheader, details: lines)
    }
}

struct FlowLayout: View {
    let skills: [String]
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 80), spacing: 6)], spacing: 6) {
            ForEach(skills, id: \.self) { skill in TagView(text: skill, color: AppTheme.primary, pill: true) }
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
