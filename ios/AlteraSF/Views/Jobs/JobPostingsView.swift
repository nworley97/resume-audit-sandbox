import SwiftUI

struct JobPostingsView: View {
    @EnvironmentObject var authVM: AuthViewModel
    @StateObject private var vm = JobsViewModel()
    @State private var showAddDept = false
    @State private var showCreateJob = false

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                VStack(spacing: 0) {
                    // Summary stats strip
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 10) {
                            SummaryChip(icon: "folder", value: "\(vm.openCount)", label: "Open roles", color: AppTheme.primary)
                            SummaryChip(icon: "pencil.line", value: "\(vm.draftCount)", label: "Drafts", color: AppTheme.warning)
                            SummaryChip(icon: "checkmark.circle", value: "\(vm.closedCount)", label: "Closed", color: AppTheme.textSecondary)
                            SummaryChip(icon: "person.2", value: "\(vm.applicantCount)", label: "Applicants", color: Color(red: 0.4, green: 0.3, blue: 0.9))
                        }
                        .padding(.horizontal, 16).padding(.vertical, 10)
                    }
                    .background(AppTheme.background)

                    Divider()

                    // Action buttons row — matching Figma
                    HStack(spacing: 10) {
                        Button {
                            showCreateJob = true
                        } label: {
                            Label("Create Job", systemImage: "plus")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundColor(AppTheme.primary)
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(AppTheme.primaryLight)
                                .cornerRadius(8)
                        }
                        Button {
                            showAddDept = true
                        } label: {
                            Label("Add Dept", systemImage: "folder.badge.plus")
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(AppTheme.textSecondary)
                                .padding(.horizontal, 14).padding(.vertical, 8)
                                .background(AppTheme.secondaryBackground)
                                .cornerRadius(8)
                        }
                        Spacer()
                    }
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(AppTheme.background)

                    Divider()

                    // Tab picker
                    Picker("Tab", selection: $vm.selectedTab) {
                        ForEach(JobsViewModel.JobTab.allCases, id: \.self) { tab in
                            Text(tab.rawValue).tag(tab)
                        }
                    }
                    .pickerStyle(.segmented)
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(AppTheme.background)

                    Divider()

                    if vm.isLoading && vm.allJobs.isEmpty {
                        Spacer()
                        ProgressView("Loading jobs…")
                        Spacer()
                    } else if let err = vm.error {
                        ErrorBanner(message: err) { Task { await vm.load() } }
                    } else {
                        ScrollView {
                            LazyVStack(spacing: 0) {
                                switch vm.selectedTab {
                                case .open:   OpenRolesContent()
                                case .drafts: DraftsContent()
                                case .closed: ClosedContent()
                                }
                            }
                            .padding(.bottom, 24)
                        }
                        .background(AppTheme.groupedBackground)
                        .refreshable { await vm.load() }
                    }
                }

                if let toast = vm.toast {
                    ToastView(message: toast)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .padding(.bottom, 16)
                }
            }
            .animation(.easeInOut(duration: 0.25), value: vm.toast)
            .navigationTitle("Job Posting")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    NavigationLink { NotificationsView() } label: {
                        Image(systemName: "bell").foregroundColor(AppTheme.textPrimary)
                    }
                    AvatarView(initials: authVM.currentUserInitials, size: 30)
                }
            }
            .sheet(isPresented: $showCreateJob) {
                EditJobView(job: nil, onSave: { _, _ in Task { await vm.load() } })
            }
            .sheet(isPresented: $showAddDept) {
                AddDepartmentSheet(isPresented: $showAddDept, onAdd: { name in
                    Task {
                        do { _ = try await APIService.shared.createDepartment(name: name) }
                        catch {}
                        await vm.load()
                    }
                })
            }
            .sheet(item: $vm.showCloseRole) { job in
                CloseRoleSheet(
                    job: job,
                    candidates: [],
                    isPresented: Binding(get: { vm.showCloseRole != nil }, set: { if !$0 { vm.showCloseRole = nil } }),
                    onClose: { hired in vm.closeRole(job, hiredCandidate: hired) }
                )
            }
            .sheet(item: $vm.showEditJob) { job in
                EditJobView(job: job, onSave: { _, _ in Task { await vm.load() } })
            }
        }
        .task { await vm.load() }
        .environmentObject(vm)
    }
}

// MARK: – Open Roles

struct OpenRolesContent: View {
    @EnvironmentObject var vm: JobsViewModel

    var body: some View {
        if vm.openDepartments().isEmpty {
            VStack(spacing: 12) {
                Image(systemName: "briefcase").font(.system(size: 40)).foregroundColor(AppTheme.textTertiary).padding(.top, 60)
                Text("No open roles").font(.headline).foregroundColor(AppTheme.textSecondary)
                Text("Tap Create Job to post your first role.").font(.subheadline).foregroundColor(AppTheme.textTertiary)
            }
            .frame(maxWidth: .infinity)
        } else {
            ForEach(vm.openDepartments()) { dept in
                VStack(alignment: .leading, spacing: 0) {
                    HStack {
                        Text(dept.name).font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
                        Text("· \(dept.openCount) open").font(.system(size: 12)).foregroundColor(AppTheme.textTertiary)
                        Spacer()
                        Button {
                            // edit dept
                        } label: {
                            Label("Edit", systemImage: "pencil").font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
                        }
                    }
                    .padding(.horizontal, 16).padding(.top, 14).padding(.bottom, 6)

                    ForEach(dept.jobs) { job in
                        JobRowView(job: job, onEdit: { vm.showEditJob = job }, onClose: { vm.showCloseRole = job }, onDelete: { vm.deleteRole(job) })
                    }
                }
                .background(AppTheme.background)
                .padding(.top, 8)
            }
        }
    }
}

// MARK: – Drafts

struct DraftsContent: View {
    @EnvironmentObject var vm: JobsViewModel
    @State private var showAll = false

    var drafts: [Job] { vm.draftJobs() }
    var visible: [Job] { showAll ? drafts : Array(drafts.prefix(4)) }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("\(drafts.count) unpublished")
                .font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
                .padding(.horizontal, 16).padding(.vertical, 10)

            ForEach(visible) { job in
                NavigationLink { EditJobView(job: job, onSave: { _, _ in Task { await vm.load() } }) } label: {
                    DraftRowView(job: job)
                }
                .swipeActions {
                    Button(role: .destructive) { vm.deleteRole(job) } label: { Label("Delete", systemImage: "trash") }
                }
            }

            if drafts.count > 4 {
                Button {
                    withAnimation { showAll.toggle() }
                } label: {
                    HStack {
                        Text(showAll ? "Show fewer" : "Show all \(drafts.count) drafts")
                            .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
                        Image(systemName: showAll ? "chevron.up" : "chevron.down")
                            .font(.system(size: 11)).foregroundColor(AppTheme.primary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 12)
                }
            }
        }
        .background(AppTheme.background).padding(.top, 8)
    }
}

// MARK: – Closed

struct ClosedContent: View {
    @EnvironmentObject var vm: JobsViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("\(vm.closedJobs().count) filled")
                .font(.system(size: 13, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
                .padding(.horizontal, 16).padding(.vertical, 10)

            ForEach(vm.closedJobs()) { job in
                ClosedJobRowView(job: job, onReopen: { vm.reopenRole(job) })
            }
        }
        .background(AppTheme.background).padding(.top, 8)
    }
}

// MARK: – Supporting Views

struct ErrorBanner: View {
    let message: String; let retry: () -> Void
    var body: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "exclamationmark.triangle").font(.system(size: 36)).foregroundColor(AppTheme.warning)
            Text(message).font(.subheadline).foregroundColor(AppTheme.textSecondary).multilineTextAlignment(.center).padding(.horizontal, 32)
            Button("Retry", action: retry).font(.system(size: 15, weight: .semibold)).foregroundColor(AppTheme.primary)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}

struct SummaryChip: View {
    let icon: String; let value: String; let label: String; let color: Color
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon).font(.system(size: 14)).foregroundColor(color)
            VStack(alignment: .leading, spacing: 0) {
                Text(value).font(.system(size: 17, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                Text(label).font(.system(size: 11)).foregroundColor(AppTheme.textSecondary)
            }
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(AppTheme.secondaryBackground).cornerRadius(10)
    }
}

struct DraftRowView: View {
    let job: Job
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(job.title).font(.system(size: 15, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                Text(job.department).font(.caption).foregroundColor(AppTheme.textSecondary)
            }
            Spacer()
            Text("Draft").font(.caption2.weight(.semibold))
                .foregroundColor(AppTheme.warning)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(AppTheme.warning.opacity(0.12)).cornerRadius(6)
        }
        .padding(.horizontal, 16).padding(.vertical, 14)
        .background(AppTheme.background)
        Divider().padding(.leading, 16)
    }
}

struct ClosedJobRowView: View {
    let job: Job; let onReopen: () -> Void
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: "checkmark.circle.fill").foregroundColor(AppTheme.success)
            VStack(alignment: .leading, spacing: 3) {
                Text(job.title).font(.system(size: 15, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                if let hired = job.hiredCandidate {
                    Text("Hired \(hired)").font(.caption).foregroundColor(AppTheme.textSecondary)
                }
            }
            Spacer()
            Button("Reopen", action: onReopen)
                .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
        }
        .padding(.horizontal, 16).padding(.vertical, 14).background(AppTheme.background)
        Divider().padding(.leading, 16)
    }
}

struct AddDepartmentSheet: View {
    @Binding var isPresented: Bool
    var onAdd: (String) -> Void = { _ in }
    @State private var name = ""
    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("Group your open roles by team.").font(.subheadline).foregroundColor(AppTheme.textSecondary)
                VStack(alignment: .leading, spacing: 6) {
                    Text("Department name").font(.subheadline.weight(.medium))
                    TextField("e.g. Customer Success", text: $name).textFieldStyle(AlteraTextFieldStyle())
                }
                Spacer()
            }
            .padding(24)
            .navigationTitle("Add department").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { isPresented = false } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add department") { onAdd(name); isPresented = false }
                        .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                        .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

struct ToastView: View {
    let message: String
    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill").foregroundColor(.white)
            Text(message).font(.subheadline.weight(.medium)).foregroundColor(.white)
        }
        .padding(.horizontal, 18).padding(.vertical, 12)
        .background(Color.black.opacity(0.85)).cornerRadius(24).shadow(radius: 8)
    }
}
