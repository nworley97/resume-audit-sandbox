import SwiftUI

struct JobDetailView: View {
    let job: Job
    var onEdit: () -> Void = {}
    var onClose: () -> Void = {}
    var onDelete: () -> Void = {}

    @State private var navigateToCandidates = false
    @State private var showActions = false
    @State private var confirmDelete = false
    @State private var copiedLink = false

    private let api = APIService.shared

    private var applicationLink: String {
        guard let slug = api.tenantSlug else { return "" }
        return AppConfig.baseURL.appendingPathComponent("\(slug)/apply/\(job.jobId)").absoluteString
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                infoCard

                if !job.description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    descriptionCard
                }

                applicationLinkCard

                Button { navigateToCandidates = true } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "person.3.fill").foregroundColor(AppTheme.primary)
                        Text("View \(job.applicantCount) Candidate\(job.applicantCount == 1 ? "" : "s")")
                            .font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                        Spacer()
                        Image(systemName: "chevron.right").font(.caption).foregroundColor(AppTheme.textTertiary)
                    }
                    .padding(14)
                    .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
                    .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
                }
                .buttonStyle(.plain)
            }
            .padding(16).padding(.bottom, 24)
        }
        .background(AppTheme.groupedBackground.ignoresSafeArea())
        .navigationTitle(job.title)
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(isPresented: $navigateToCandidates) {
            CandidatesView(filterJobId: job.jobId)
        }
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button { showActions = true } label: {
                    Image(systemName: "ellipsis").foregroundColor(AppTheme.textPrimary)
                }
            }
        }
        .sheet(isPresented: $showActions) {
            JobActionsSheet(
                job: job,
                onViewCandidates: { navigateToCandidates = true },
                onEdit: onEdit,
                onClose: onClose,
                onDelete: { confirmDelete = true }
            )
        }
        .alert("Delete this role?", isPresented: $confirmDelete) {
            Button("Delete", role: .destructive) { onDelete() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("\"\(job.title)\" and all its data will be permanently removed.")
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                JobStatusTag(status: job.status)
                Spacer()
                Text(job.jobId).font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
            }
            Text(job.title).font(.system(size: 22, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text("Posted \(job.postedDate.formatted(.dateTime.month(.abbreviated).day().year()))")
                .font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
        }
    }

    private var infoCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            infoRow(icon: "building.2", label: "Department", value: job.department.isEmpty ? "\u{2014}" : job.department)
            infoRow(icon: "mappin.and.ellipse", label: "Location", value: job.location.isEmpty ? "\u{2014}" : job.location)
            infoRow(icon: "briefcase", label: "Employment type", value: job.employmentType.rawValue)
            infoRow(icon: "laptopcomputer", label: "Work arrangement", value: job.workArrangement.rawValue)
            if job.salaryMin > 0 || job.salaryMax > 0 {
                infoRow(icon: "dollarsign.circle", label: "Salary range", value: "$\(job.salaryMin)\u{2013}$\(job.salaryMax)")
            }
            infoRow(icon: "person.2", label: "Applicants", value: "\(job.applicantCount)")
            infoRow(icon: "diamond", label: "Diamonds found", value: "\(job.diamondCount)")
            infoRow(icon: "checkmark.shield", label: "Self-ID survey", value: job.idSurveysEnabled ? "Enabled" : "Disabled")
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }

    private func infoRow(icon: String, label: String, value: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary).frame(width: 18)
            Text(label).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
            Spacer()
            Text(value).font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.textPrimary)
        }
    }

    private var descriptionCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Role Description").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text(job.description).font(.system(size: 14)).foregroundColor(AppTheme.textSecondary)
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }

    private var applicationLinkCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Application Link").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text("Share this link on your website, social media, or job boards.")
                .font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
            HStack(spacing: 8) {
                Text(applicationLink)
                    .font(.system(size: 12))
                    .foregroundColor(AppTheme.textSecondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                Button {
                    UIPasteboard.general.string = applicationLink
                    copiedLink = true
                    Task {
                        try? await Task.sleep(nanoseconds: 2_000_000_000)
                        copiedLink = false
                    }
                } label: {
                    Label(copiedLink ? "Copied" : "Copy", systemImage: copiedLink ? "checkmark" : "doc.on.doc")
                        .font(.system(size: 12, weight: .semibold))
                }
                .buttonStyle(.bordered)
                .tint(AppTheme.primary)
            }
            .padding(10)
            .background(AppTheme.groupedBackground).cornerRadius(8)
        }
        .padding(16)
        .background(AppTheme.background).cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }
}
