import SwiftUI

struct CandidatesView: View {
    var filterJobId: String? = nil   // jd_code when drilling in from a job row

    @EnvironmentObject var authVM: AuthViewModel
    @StateObject private var vm: CandidatesViewModel
    // Needed for the "grouped" all-candidates view
    @StateObject private var jobsVM = JobsViewModel()

    init(filterJobId: String? = nil) {
        self.filterJobId = filterJobId
        _vm = StateObject(wrappedValue: CandidatesViewModel(filterJobId: filterJobId))
    }

    var body: some View {
        mainContent
            .navigationTitle(filterJobId == nil ? "Candidates" : "Candidates")
            .navigationBarTitleDisplayMode(.large)
            .task {
                if filterJobId == nil { await jobsVM.load() }
                await vm.load(jobCode: filterJobId)
            }
            .onChange(of: vm.searchText) { _ in vm.triggerSearch(jobCode: filterJobId) }
            .onChange(of: vm.sortOption) { _ in Task { await vm.load(jobCode: filterJobId) } }
            .onChange(of: vm.selectedTab) { _ in /* filter locally */ }
            .toolbar {
                ToolbarItemGroup(placement: .navigationBarTrailing) {
                    Button { vm.showFilterSheet = true } label: {
                        Image(systemName: "line.3.horizontal.decrease.circle")
                    }
                    Button { vm.showSortSheet = true } label: {
                        Image(systemName: "arrow.up.arrow.down")
                    }
                }
            }
            .sheet(isPresented: $vm.showFilterSheet) { FilterSheet(vm: vm) }
            .sheet(isPresented: $vm.showSortSheet) { SortSheet(vm: vm) }
    }

    @ViewBuilder
    private var mainContent: some View {
        VStack(spacing: 0) {
            // Tab bar
            tabBar

            Divider()

            // Search
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").foregroundColor(AppTheme.textSecondary)
                TextField("Search candidates…", text: $vm.searchText).font(.system(size: 15))
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(AppTheme.secondaryBackground).cornerRadius(10)
            .padding(.horizontal, 16).padding(.vertical, 8)
            .background(AppTheme.background)

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

    private var tabBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 0) {
                ForEach(CandidatesViewModel.CandidateTab.allCases, id: \.self) { tab in
                    Button { vm.selectedTab = tab } label: {
                        VStack(spacing: 4) {
                            HStack(spacing: 4) {
                                if tab == .diamonds { Image(systemName: "diamond.fill").font(.system(size: 11)).foregroundColor(AppTheme.diamond) }
                                else if tab == .flagged { Image(systemName: "flag.fill").font(.system(size: 11)).foregroundColor(AppTheme.flagged) }
                                Text(tab.rawValue).font(.system(size: 14, weight: .medium))
                                Text(countFor(tab))
                                    .font(.system(size: 12, weight: .bold))
                                    .padding(.horizontal, 6).padding(.vertical, 2)
                                    .background(vm.selectedTab == tab ? AppTheme.primary : AppTheme.secondaryBackground)
                                    .foregroundColor(vm.selectedTab == tab ? .white : AppTheme.textSecondary)
                                    .cornerRadius(10)
                            }
                            Rectangle().frame(height: 2)
                                .foregroundColor(vm.selectedTab == tab ? AppTheme.primary : .clear)
                        }
                        .foregroundColor(vm.selectedTab == tab ? AppTheme.primary : AppTheme.textSecondary)
                        .padding(.horizontal, 16).padding(.vertical, 12)
                    }
                }
            }
        }
        .background(AppTheme.background)
    }

    @ViewBuilder
    private var candidateList: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                if filterJobId != nil {
                    // Flat list for single-role view
                    ForEach(vm.displayedCandidates) { candidate in
                        NavigationLink { candidateProfile(candidate) } label: {
                            CandidateRowView(candidate: candidate)
                        }
                    }
                } else {
                    // Grouped by job
                    let groups = vm.grouped(allJobs: jobsVM.allJobs)
                    ForEach(groups, id: \.job.id) { group in
                        GroupHeaderRow(job: group.job, count: group.candidates.count)
                        ForEach(group.candidates.prefix(3)) { candidate in
                            NavigationLink { candidateProfile(candidate) } label: {
                                CandidateRowView(candidate: candidate)
                            }
                        }
                        if group.candidates.count > 3 {
                            NavigationLink { CandidatesView(filterJobId: group.job.jobId) } label: {
                                Text("View all \(group.candidates.count)")
                                    .font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.primary)
                                    .frame(maxWidth: .infinity).padding(.vertical, 10)
                                    .background(AppTheme.background)
                            }
                        }
                        Divider().padding(.vertical, 4)
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
            .padding(.bottom, 24)
        }
        .background(AppTheme.groupedBackground)
        .refreshable { await vm.load(jobCode: filterJobId) }
    }

    @ViewBuilder
    private func candidateProfile(_ candidate: Candidate) -> some View {
        CandidateProfileView(
            candidateId: candidate.id,
            preloaded: candidate
        )
    }

    private func countFor(_ tab: CandidatesViewModel.CandidateTab) -> String {
        switch tab {
        case .all: return "\(vm.totalCount)"
        case .diamonds: return "\(vm.diamondCount)"
        case .flagged: return "\(vm.flaggedCount)"
        }
    }
}

struct GroupHeaderRow: View {
    let job: Job
    let count: Int
    var body: some View {
        HStack {
            Text(job.title).font(.system(size: 14, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
            Spacer()
            Text("\(count)").font(.system(size: 12, weight: .bold)).foregroundColor(.white)
                .padding(.horizontal, 8).padding(.vertical, 3)
                .background(AppTheme.primary).cornerRadius(10)
            Image(systemName: "chevron.right").font(.caption).foregroundColor(AppTheme.textTertiary)
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(AppTheme.background)
    }
}

struct FilterSheet: View {
    @ObservedObject var vm: CandidatesViewModel
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section("Department") {
                    Button { vm.selectedDepartment = nil } label: {
                        HStack { Text("All departments"); Spacer()
                            if vm.selectedDepartment == nil { Image(systemName: "checkmark").foregroundColor(AppTheme.primary) }
                        }
                    }.foregroundColor(AppTheme.textPrimary)
                }
            }
            .navigationTitle("Filter").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.foregroundColor(AppTheme.primary) } }
        }
        .presentationDetents([.medium])
    }
}

struct SortSheet: View {
    @ObservedObject var vm: CandidatesViewModel
    @Environment(\.dismiss) var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section("Sort candidates") {
                    ForEach(CandidatesViewModel.SortOption.allCases, id: \.self) { option in
                        Button { vm.sortOption = option } label: {
                            HStack { Text(option.rawValue); Spacer()
                                if vm.sortOption == option { Image(systemName: "checkmark").foregroundColor(AppTheme.primary) }
                            }
                        }.foregroundColor(AppTheme.textPrimary)
                    }
                }
            }
            .navigationTitle("Sort").navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.foregroundColor(AppTheme.primary) } }
        }
        .presentationDetents([.medium])
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
