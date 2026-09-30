import SwiftUI

struct CandidatesView: View {
    var filterJobId: String? = nil   // jd_code when drilling in from a job row
    var filterJobTitle: String? = nil

    @EnvironmentObject var authVM: AuthViewModel
    @StateObject private var vm: CandidatesViewModel
    // Needed for the "grouped" all-candidates view
    @StateObject private var jobsVM = JobsViewModel()
    @State private var previewCandidate: Candidate?
    @State private var fullProfileCandidate: Candidate?
    @State private var pendingFullProfileCandidate: Candidate?
    @State private var showDepartmentFilterSheet = false
    @State private var showSortSheet = false

    init(filterJobId: String? = nil, filterJobTitle: String? = nil) {
        self.filterJobId = filterJobId
        self.filterJobTitle = filterJobTitle
        _vm = StateObject(wrappedValue: CandidatesViewModel(filterJobId: filterJobId))
    }

    var body: some View {
        NavigationStackWrapper(filterJobId: filterJobId) {
            content
        }
    }

    @ViewBuilder
    private var content: some View {
        mainContent
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(filterJobId == nil ? .hidden : .automatic, for: .navigationBar)
            .task {
                if filterJobId == nil {
                    async let jobs: () = jobsVM.load()
                    await vm.load(jobCode: filterJobId)
                    await jobs
                } else {
                    await vm.load(jobCode: filterJobId)
                }
            }
            .onChange(of: vm.searchText) { _ in vm.triggerSearch(jobCode: filterJobId) }
            .onChange(of: vm.sortOption) { _ in Task { await vm.load(jobCode: filterJobId) } }
            .onChange(of: vm.selectedDepartment) { _ in Task { await vm.load(jobCode: filterJobId) } }
            .onChange(of: vm.selectedTab) { _ in /* filter locally */ }
            .sheet(item: $previewCandidate, onDismiss: {
                if let candidate = pendingFullProfileCandidate {
                    pendingFullProfileCandidate = nil
                    fullProfileCandidate = candidate
                }
            }) { candidate in
                CandidateQuickPreviewSheet(candidate: candidate, onViewFullProfile: {
                    pendingFullProfileCandidate = candidate
                    previewCandidate = nil
                })
            }
            .sheet(item: $fullProfileCandidate) { candidate in
                NavigationStack {
                    CandidateProfileView(candidateId: candidate.id, preloaded: candidate)
                        .toolbar {
                            ToolbarItem(placement: .navigationBarLeading) {
                                Button("Close") { fullProfileCandidate = nil }
                            }
                        }
                }
            }
            .sheet(isPresented: $showDepartmentFilterSheet) {
                DepartmentFilterSheet(selection: $vm.selectedDepartment, departments: jobsVM.allDepartments)
            }
            .sheet(isPresented: $showSortSheet) {
                SelectionListSheet(title: "Sort", options: CandidatesViewModel.SortOption.allCases, selection: $vm.sortOption) { $0.rawValue }
            }
    }

    @ViewBuilder
    private var mainContent: some View {
        VStack(spacing: 0) {
            if filterJobId == nil {
                AppTopBar()
                header
            } else {
                VStack(alignment: .leading, spacing: 4) {
                    Text(filterJobTitle ?? filterJobId ?? "")
                        .font(.figtree(size: 13)).foregroundColor(AppTheme.textSecondary)
                    Text("\(vm.totalCount) Candidates")
                        .font(AppTheme.pageTitle).foregroundColor(AppTheme.textPrimary)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16).padding(.bottom, 12)
            }

            // Search
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundColor(AppTheme.textSecondary)
                TextField("Search roles or candidates…", text: $vm.searchText).font(.figtree(size: 15))
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(AppTheme.secondaryBackground).cornerRadius(10)
            .padding(.horizontal, 16).padding(.top, 4).padding(.bottom, 8)
            .background(filterJobId == nil ? AppTheme.pageBackground : AppTheme.groupedBackground)

            if filterJobId == nil {
                filterPills
            }

            Divider()

            if (vm.isLoading || (filterJobId == nil && jobsVM.isLoading)) && vm.candidates.isEmpty {
                Spacer()
                ProgressView("Loading candidates…")
                Spacer()
            } else if let err = vm.error {
                ErrorBanner(message: err) { Task { await vm.load(jobCode: filterJobId) } }
            } else if filterJobId == nil, let err = jobsVM.error {
                ErrorBanner(message: err) { Task { await jobsVM.load() } }
            } else {
                candidateList
            }
        }
        .background(filterJobId == nil ? AppTheme.pageBackground : AppTheme.groupedBackground)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Candidates")
                .font(AppTheme.pageTitle)
                .foregroundColor(AppTheme.textPrimary)
            Text("Review and compare applicants across your open roles.")
                .font(.figtree(size: 15))
                .foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16).padding(.top, 4).padding(.bottom, 16)
    }

    private var filterPills: some View {
        HStack(spacing: 10) {
            Button { showDepartmentFilterSheet = true } label: {
                FilterPill(text: vm.selectedDepartment ?? "All departments")
            }

            Button { showSortSheet = true } label: {
                FilterPill(text: vm.sortOption.rawValue)
            }

            Spacer()
        }
        .padding(.horizontal, 16).padding(.bottom, 10)
    }

    @ViewBuilder
    private var candidateList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                if filterJobId != nil {
                    // Flat list for single-role view
                    ForEach(vm.displayedCandidates) { candidate in
                        Button { previewCandidate = candidate } label: {
                            CandidateRowView(candidate: candidate, showsJobTitle: false)
                        }
                        .buttonStyle(.plain)
                    }
                } else {
                    // Grouped by job
                    let groups = vm.grouped(allJobs: jobsVM.allJobs)
                    ForEach(groups, id: \.job.id) { group in
                        GroupHeaderRow(job: group.job, count: group.total)
                        ForEach(group.candidates.prefix(3)) { candidate in
                            Button { previewCandidate = candidate } label: {
                                CandidateRowView(candidate: candidate)
                            }
                            .buttonStyle(.plain)
                        }
                        Spacer(minLength: 8)
                    }
                }

                if let error = vm.pageError {
                    Text(error).font(.figtree(size: 13)).foregroundColor(AppTheme.danger).padding()
                }
                if vm.hasMore {
                    Button {
                        Task { await vm.loadMore(jobCode: filterJobId) }
                    } label: {
                        if vm.isLoadingMore { ProgressView() }
                        else { Text("Load more candidates (\(vm.candidates.count) of \(vm.totalCount))") }
                    }
                    .disabled(vm.isLoadingMore || vm.isLoading)
                    .padding()
                }

                if vm.candidates.isEmpty && !vm.isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "person.2.slash")
                            .font(.figtree(size: 40)).foregroundColor(AppTheme.textTertiary).padding(.top, 48)
                        Text("No candidates yet").font(.figtree(size: 17, weight: .semibold)).foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.bottom, 24)
        }
        .background(AppTheme.groupedBackground)
        .refreshable { await vm.load(jobCode: filterJobId) }
    }


}

struct GroupHeaderRow: View {
    let job: Job
    let count: Int
    var body: some View {
        HStack {
            Text(job.title).font(.figtree(size: 16, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text("\(count)").font(.figtree(size: 12, weight: .bold)).foregroundColor(.white)
                .padding(.horizontal, 7).padding(.vertical, 2)
                .background(AppTheme.primary).cornerRadius(9)
            Spacer()
            NavigationLink {
                CandidatesView(filterJobId: job.jobId, filterJobTitle: job.title)
            } label: {
                HStack(spacing: 2) {
                    Text("View").font(.figtree(size: 13, weight: .medium))
                    Image(systemName: "chevron.right").font(.figtree(size: 11, weight: .semibold))
                }
                .foregroundColor(AppTheme.primary)
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
    }
}

struct DepartmentFilterSheet: View {
    @Binding var selection: String?
    let departments: [APIDepartment]
    @Environment(\.dismiss) var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Text("Filter by department").font(.figtree(size: 18, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                    .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 12)
                row(label: "All departments", isSelected: selection == nil) {
                    selection = nil
                    dismiss()
                }
                ForEach(departments, id: \.id) { dept in
                    row(label: dept.name, isSelected: selection == dept.name) {
                        selection = dept.name
                        dismiss()
                    }
                }
                Spacer(minLength: 8)
        }
        .padding(.bottom, 16)
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    private func row(label: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(label).font(.figtree(size: 16)).foregroundColor(isSelected ? AppTheme.primary : AppTheme.textPrimary)
                Spacer()
                if isSelected { Image(systemName: "checkmark").foregroundColor(AppTheme.primary) }
            }
            .padding(.horizontal, 20).padding(.vertical, 14)
            .background(isSelected ? AppTheme.primaryLight : Color.clear)
        }
        .buttonStyle(.plain)
    }
}

private struct FilterPill: View {
    let text: String
    var body: some View {
        HStack(spacing: 4) {
            Text(text).font(.figtree(size: 13, weight: .medium)).lineLimit(1)
            Image(systemName: "chevron.down").font(.figtree(size: 10, weight: .semibold))
        }
        .foregroundColor(AppTheme.textPrimary)
        .padding(.horizontal, 12).padding(.vertical, 5)
        .background(AppTheme.secondaryBackground)
        .cornerRadius(20)
    }
}

// Wrapper that only adds NavigationStack when not already inside one
struct NavigationStackWrapper<Content: View>: View {
    let filterJobId: String?
    @ViewBuilder let content: () -> Content
    var body: some View {
        if filterJobId == nil { NavigationStack { content() } } else { content() }
    }
}
