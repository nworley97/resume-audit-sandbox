import SwiftUI

struct CandidatesView: View {
    var filterJobId: String? = nil   // jd_code when drilling in from a job row

    @EnvironmentObject var authVM: AuthViewModel
    @StateObject private var vm: CandidatesViewModel
    // Needed for the "grouped" all-candidates view
    @StateObject private var jobsVM = JobsViewModel()
    @State private var previewCandidate: Candidate?
    @State private var fullProfileCandidate: Candidate?
    @State private var showDepartmentFilterSheet = false
    @State private var showSortSheet = false

    init(filterJobId: String? = nil) {
        self.filterJobId = filterJobId
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
            .navigationTitle("Candidates")
            .navigationBarTitleDisplayMode(.large)
            .toolbar(filterJobId == nil ? .hidden : .automatic, for: .navigationBar)
            .task {
                if filterJobId == nil { await jobsVM.load() }
                await vm.load(jobCode: filterJobId)
            }
            .onChange(of: vm.searchText) { _ in vm.triggerSearch(jobCode: filterJobId) }
            .onChange(of: vm.sortOption) { _ in Task { await vm.load(jobCode: filterJobId) } }
            .onChange(of: vm.selectedTab) { _ in /* filter locally */ }
            .sheet(item: $previewCandidate) { candidate in
                CandidateQuickPreviewSheet(candidate: candidate, onViewFullProfile: {
                    previewCandidate = nil
                    fullProfileCandidate = candidate
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
                SelectionListSheet(title: "Sort candidates", options: CandidatesViewModel.SortOption.allCases, selection: $vm.sortOption) { $0.rawValue }
            }
    }

    @ViewBuilder
    private var mainContent: some View {
        VStack(spacing: 0) {
            if filterJobId == nil {
                AppTopBar()
                header
            }

            // Search
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundColor(AppTheme.textSecondary)
                TextField("Search roles or candidates…", text: $vm.searchText).font(.system(size: 15))
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(AppTheme.secondaryBackground).cornerRadius(10)
            .padding(.horizontal, 16).padding(.top, 4).padding(.bottom, 8)
            .background(AppTheme.background)

            if filterJobId == nil {
                filterPills
            }

            Divider()

            if vm.isLoading && vm.candidates.isEmpty {
                Spacer()
                ProgressView("Loading candidates…")
                Spacer()
            } else if let err = vm.error {
                ErrorBanner(message: err) { Task { await vm.load(jobCode: filterJobId) } }
            } else {
                candidateList
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("Candidates")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(AppTheme.textPrimary)
            Text("Review and compare applicants across your open roles.")
                .font(.system(size: 13))
                .foregroundColor(AppTheme.textSecondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16).padding(.top, 8).padding(.bottom, 12)
    }

    private var filterPills: some View {
        HStack(spacing: 10) {
            Button { showDepartmentFilterSheet = true } label: {
                FilterPill(text: vm.selectedDepartment ?? "All departments")
            }

            Button { showSortSheet = true } label: {
                FilterPill(text: "Sort: \(vm.sortOption.rawValue)")
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
                            CandidateRowView(candidate: candidate)
                        }
                        .buttonStyle(.plain)
                    }
                } else {
                    // Grouped by job
                    let groups = vm.grouped(allJobs: jobsVM.allJobs)
                    ForEach(groups, id: \.job.id) { group in
                        GroupHeaderRow(job: group.job, count: group.candidates.count)
                        ForEach(group.candidates.prefix(3)) { candidate in
                            Button { previewCandidate = candidate } label: {
                                CandidateRowView(candidate: candidate)
                            }
                            .buttonStyle(.plain)
                        }
                        Spacer(minLength: 8)
                    }
                }

                if vm.candidates.isEmpty && !vm.isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "person.2.slash")
                            .font(.system(size: 40)).foregroundColor(AppTheme.textTertiary).padding(.top, 48)
                        Text("No candidates yet").font(.headline).foregroundColor(AppTheme.textSecondary)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.bottom, 100)
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
            Text(job.title).font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
            Text("\(count)").font(.system(size: 12, weight: .bold)).foregroundColor(.white)
                .padding(.horizontal, 7).padding(.vertical, 2)
                .background(AppTheme.primary).cornerRadius(9)
            Spacer()
            NavigationLink {
                CandidatesView(filterJobId: job.jobId)
            } label: {
                HStack(spacing: 2) {
                    Text("View").font(.system(size: 13, weight: .medium))
                    Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold))
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
        VStack(alignment: .leading, spacing: 0) {
            Text("Filter by department").font(.system(size: 18, weight: .bold)).foregroundColor(AppTheme.textPrimary)
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
        .presentationDetents([.medium])
    }

    private func row(label: String, isSelected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(label).font(.system(size: 16)).foregroundColor(isSelected ? AppTheme.primary : AppTheme.textPrimary)
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
            Text(text).font(.system(size: 13, weight: .medium)).lineLimit(1)
            Image(systemName: "chevron.down").font(.system(size: 10, weight: .semibold))
        }
        .foregroundColor(AppTheme.textPrimary)
        .padding(.horizontal, 12).padding(.vertical, 8)
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
