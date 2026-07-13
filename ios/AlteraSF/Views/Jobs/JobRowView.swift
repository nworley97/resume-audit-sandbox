import SwiftUI

struct JobRowView: View {
    let job: Job
    var onEdit: () -> Void = {}
    var onClose: () -> Void = {}
    var onDelete: () -> Void = {}

    @State private var showActions = false
    @State private var confirmDelete = false
    @State private var navigateToCandidates = false

    var body: some View {
        VStack(spacing: 0) {
            // Title row + three-dot menu
            HStack(alignment: .top, spacing: 8) {
                Circle()
                    .fill(job.status == .open ? AppTheme.success : AppTheme.textTertiary)
                    .frame(width: 8, height: 8)
                    .padding(.top, 5)
                Text(job.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(AppTheme.textPrimary)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Button {
                    showActions = true
                } label: {
                    Image(systemName: "ellipsis")
                        .font(.system(size: 16))
                        .foregroundColor(AppTheme.textSecondary)
                        .padding(8)
                        .contentShape(Rectangle())
                }
            }
            .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 2)

            // Job ID + posted date
            Text("\(job.jobId)  ·  Posted \(job.postedDate.formatted(.dateTime.month(.abbreviated).day()))")
                .font(.system(size: 12))
                .foregroundColor(AppTheme.textSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)

            // Applicants + chevron
            HStack(spacing: 10) {
                StackedAvatars(initials: job.avatarInitials)
                Text("\(job.applicantCount) applicants")
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundColor(AppTheme.textTertiary)
            }
            .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 14)

            Divider().padding(.leading, 16)
        }
        .background(AppTheme.background)
        .contentShape(Rectangle())
        .onTapGesture { navigateToCandidates = true }
        .navigationDestination(isPresented: $navigateToCandidates) {
            CandidatesView(filterJobId: job.jobId)
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
}

struct JobActionsSheet: View {
    @Environment(\.dismiss) var dismiss
    let job: Job
    let onViewCandidates: () -> Void
    let onEdit: () -> Void
    let onClose: () -> Void
    let onDelete: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 2) {
                Text(job.title)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(AppTheme.textPrimary)
                Text("\(job.jobId) · \(job.applicantCount) applicants")
                    .font(.system(size: 13))
                    .foregroundColor(AppTheme.textSecondary)
            }
            .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 16)

            actionRow(icon: "eye", label: "View candidates", tint: AppTheme.textPrimary) {
                dismiss(); onViewCandidates()
            }
            actionRow(icon: "pencil", label: "Edit role", tint: AppTheme.textPrimary) {
                dismiss(); onEdit()
            }
            actionRow(icon: "lock", label: "Close role", tint: AppTheme.textPrimary) {
                dismiss(); onClose()
            }
            actionRow(icon: "trash", label: "Delete role", tint: AppTheme.danger) {
                dismiss(); onDelete()
            }

            Button("Cancel") { dismiss() }
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(AppTheme.textPrimary)
                .frame(maxWidth: .infinity).frame(height: 48)
                .background(AppTheme.secondaryBackground)
                .cornerRadius(AppTheme.buttonCornerRadius)
                .padding(.horizontal, 16).padding(.top, 12)
        }
        .padding(.bottom, 16)
        .presentationDetents([.height(340)])
    }

    private func actionRow(icon: String, label: String, tint: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 14) {
                Image(systemName: icon).font(.system(size: 16)).foregroundColor(tint).frame(width: 20)
                Text(label).font(.system(size: 16)).foregroundColor(tint)
                Spacer()
            }
            .padding(.horizontal, 20).padding(.vertical, 13)
        }
    }
}
