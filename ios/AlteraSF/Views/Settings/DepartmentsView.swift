import SwiftUI

struct DepartmentsView: View {
    @State private var departments: [APIDepartment] = []
    @State private var isLoading = false
    @State private var error: String? = nil
    @State private var showAdd = false
    @State private var newDeptName = ""
    @State private var isAdding = false

    private let api = APIService.shared

    var body: some View {
        List {
            if isLoading && departments.isEmpty {
                HStack { Spacer(); ProgressView(); Spacer() }.listRowBackground(Color.clear)
            } else if let err = error {
                Text(err).foregroundColor(AppTheme.danger).font(.caption)
            } else {
                Section("\(departments.count) departments") {
                    ForEach(departments, id: \.id) { dept in
                        HStack(spacing: 14) {
                            Circle()
                                .fill(colorFor(dept.name))
                                .frame(width: 10, height: 10)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(dept.name)
                                    .font(.system(size: 15, weight: .medium))
                                    .foregroundColor(AppTheme.textPrimary)
                                Text(dept.teamLead.isEmpty ? "No lead assigned" : dept.teamLead)
                                    .font(.system(size: 12))
                                    .foregroundColor(AppTheme.textSecondary)
                            }
                            Spacer()
                            Image(systemName: "chevron.right").font(.caption).foregroundColor(AppTheme.textTertiary)
                        }
                        .padding(.vertical, 4)
                    }
                    .onDelete(perform: deleteDepts)
                }
            }
        }
        .navigationTitle("Departments")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showAdd = true
                } label: {
                    Image(systemName: "plus").foregroundColor(AppTheme.primary)
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
        .alert("New Department", isPresented: $showAdd) {
            TextField("Department name", text: $newDeptName)
            Button("Add") { Task { await addDept() } }
                .disabled(newDeptName.trimmingCharacters(in: .whitespaces).isEmpty)
            Button("Cancel", role: .cancel) { newDeptName = "" }
        } message: {
            Text("Enter a name for the new department.")
        }
    }

    private func load() async {
        isLoading = true
        error = nil
        do {
            departments = try await api.fetchDepartments()
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func addDept() async {
        let name = newDeptName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        newDeptName = ""
        do {
            let dept = try await api.createDepartment(name: name)
            departments.append(dept)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func deleteDepts(at offsets: IndexSet) {
        let toDelete = offsets.map { departments[$0] }
        departments.remove(atOffsets: offsets)
        for dept in toDelete {
            Task { try? await api.deleteDepartment(id: dept.id) }
        }
    }

    private func colorFor(_ name: String) -> Color {
        let colors: [Color] = [AppTheme.primary, AppTheme.warning, AppTheme.success, .purple, .orange, .pink]
        return colors[abs(name.hashValue) % colors.count]
    }
}
