import SwiftUI

@MainActor
final class TeamViewModel: ObservableObject {
    @Published var members: [APITeamMember] = []
    @Published var isLoading = false
    @Published var error: String? = nil
    @Published var lastInvitedTempPassword: String? = nil

    private let api = APIService.shared

    func load() async {
        isLoading = true
        error = nil
        do {
            members = try await api.fetchTeam()
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    func invite(name: String, email: String, role: String) async -> Bool {
        error = nil
        do {
            let member = try await api.inviteTeamMember(name: name, email: email, role: role)
            members.append(member)
            lastInvitedTempPassword = member.tempPassword
            return true
        } catch {
            self.error = error.localizedDescription
            return false
        }
    }

    func updateRole(_ member: APITeamMember, role: String) async {
        do {
            let updated = try await api.updateTeamMemberRole(id: member.id, role: role)
            if let idx = members.firstIndex(where: { $0.id == member.id }) {
                members[idx] = updated
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    func remove(_ member: APITeamMember) async {
        do {
            try await api.removeTeamMember(id: member.id)
            members.removeAll { $0.id == member.id }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct TeamView: View {
    @StateObject private var vm = TeamViewModel()
    @State private var showInviteSheet = false
    @State private var showTempPasswordAlert = false

    var body: some View {
        List {
            if vm.isLoading && vm.members.isEmpty {
                HStack { Spacer(); ProgressView(); Spacer() }.listRowBackground(Color.clear)
            } else if let err = vm.error, vm.members.isEmpty {
                ErrorBanner(message: err) { Task { await vm.load() } }
            } else {
                Section("\(vm.members.count) members") {
                    ForEach(vm.members) { member in
                        HStack(spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(roleColor(member.role).opacity(0.15))
                                    .frame(width: 40, height: 40)
                                Text(member.initials)
                                    .font(.system(size: 14, weight: .bold))
                                    .foregroundColor(roleColor(member.role))
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text(member.name).font(.system(size: 14, weight: .medium)).foregroundColor(AppTheme.textPrimary)
                                Text(member.email).font(.system(size: 12)).foregroundColor(AppTheme.textSecondary)
                            }
                            Spacer()
                            Menu {
                                ForEach(["admin", "manager", "viewer"], id: \.self) { role in
                                    Button(role.capitalized) { Task { await vm.updateRole(member, role: role) } }
                                }
                            } label: {
                                RolePill(role: member.role)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                    .onDelete { idx in
                        for i in idx { Task { await vm.remove(vm.members[i]) } }
                    }
                }
            }
        }
        .navigationTitle("Team")
        .navigationBarTitleDisplayMode(.large)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showInviteSheet = true
                } label: {
                    Label("Invite", systemImage: "person.badge.plus")
                        .foregroundColor(AppTheme.primary)
                }
            }
        }
        .task { await vm.load() }
        .refreshable { await vm.load() }
        .sheet(isPresented: $showInviteSheet) {
            InviteTeamMemberSheet { name, email, role in
                let ok = await vm.invite(name: name, email: email, role: role)
                if ok && vm.lastInvitedTempPassword != nil { showTempPasswordAlert = true }
                return ok
            }
        }
        .alert("Member invited", isPresented: $showTempPasswordAlert) {
            Button("Done") { vm.lastInvitedTempPassword = nil }
        } message: {
            Text("Temporary password: \(vm.lastInvitedTempPassword ?? "")\n\nShare this with them securely — they should change it after signing in.")
        }
    }

    private func roleColor(_ role: String) -> Color {
        switch role {
        case "admin": return AppTheme.primary
        case "manager": return AppTheme.warning
        default: return AppTheme.textSecondary
        }
    }
}

struct RolePill: View {
    let role: String
    private var color: Color {
        switch role {
        case "admin": return AppTheme.primary
        case "manager": return AppTheme.warning
        default: return AppTheme.textSecondary
        }
    }
    var body: some View {
        Text(role.capitalized)
            .font(.system(size: 11, weight: .semibold))
            .foregroundColor(color)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(color.opacity(0.12))
            .cornerRadius(6)
    }
}

struct InviteTeamMemberSheet: View {
    @Environment(\.dismiss) var dismiss
    let onAdd: (String, String, String) async -> Bool
    @State private var name = ""
    @State private var email = ""
    @State private var role = "manager"
    @State private var isSaving = false
    @State private var error: String? = nil

    var body: some View {
        NavigationStack {
            Form {
                Section("Member details") {
                    TextField("Full name", text: $name)
                    TextField("Email address", text: $email)
                        .keyboardType(.emailAddress).autocapitalization(.none)
                }
                Section {
                    Picker("Role", selection: $role) {
                        Text("Admin").tag("admin")
                        Text("Manager").tag("manager")
                        Text("Viewer").tag("viewer")
                    }
                    .pickerStyle(.inline)
                } header: {
                    Text("Role")
                } footer: {
                    Text("Admins can manage billing and team members. Managers can post jobs and review candidates. Viewers have read-only access.")
                }
                if let err = error {
                    Section {
                        Text(err).foregroundColor(AppTheme.danger).font(.caption)
                    }
                }
            }
            .navigationTitle("Invite member")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView().scaleEffect(0.8)
                    } else {
                        Button("Send invite") {
                            Task {
                                isSaving = true
                                let ok = await onAdd(name, email, role)
                                isSaving = false
                                if ok { dismiss() } else { error = "Could not invite member. Check the seat limit on your plan." }
                            }
                        }
                        .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                        .disabled(name.isEmpty || email.isEmpty)
                    }
                }
            }
        }
        .presentationDetents([.medium])
    }
}
