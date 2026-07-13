import SwiftUI

struct EditJobView: View {
    @Environment(\.dismiss) var dismiss
    let job: Job?
    var onSave: ((Job?, String) -> Void)? = nil

    @State private var title: String
    @State private var code: String
    @State private var department: String
    @State private var location: String
    @State private var employmentType: EmploymentType
    @State private var workArrangement: WorkArrangement
    @State private var salaryRange: String
    @State private var description: String
    @State private var numberOfQuestions: Int
    @State private var startDate = Date()
    @State private var endDate = Date().addingTimeInterval(86400 * 30)
    @State private var isSaving = false
    @State private var saveError: String? = nil
    @State private var showPublishConfirm = false
    @State private var availableDepartments: [APIDepartment] = []
    @State private var showAddDepartment = false
    @State private var newDepartmentName = ""
    @State private var departmentError: String? = nil

    @State private var showDepartmentSheet = false
    @State private var showEmploymentSheet = false
    @State private var showArrangementSheet = false
    @State private var showStartDateSheet = false
    @State private var showStartTimeSheet = false
    @State private var showEndDateSheet = false
    @State private var showEndTimeSheet = false
    @State private var showQuestionCountSheet = false

    private let api = APIService.shared

    init(job: Job?, onSave: ((Job?, String) -> Void)? = nil) {
        self.job = job
        self.onSave = onSave
        _title = State(initialValue: job?.title ?? "")
        _code = State(initialValue: job?.jobId ?? "")
        _department = State(initialValue: job?.department ?? "")
        _location = State(initialValue: job?.location ?? "Remote")
        _employmentType = State(initialValue: job?.employmentType ?? .fullTime)
        _workArrangement = State(initialValue: job?.workArrangement ?? .remote)
        _salaryRange = State(initialValue: job.map { "\($0.salaryMin > 0 ? "$\($0.salaryMin)" : "")–$\($0.salaryMax > 0 ? "\($0.salaryMax)" : "")" } ?? "")
        _description = State(initialValue: job?.description ?? "")
        _numberOfQuestions = State(initialValue: job?.numberOfQuestions ?? 3)
    }

    var isNew: Bool { job == nil }

    var body: some View {
        NavigationStack {
            ZStack(alignment: .bottom) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        card {
                            Text("Basic Information").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)

                            fieldLabel("Job Title", required: true)
                            borderedTextField("e.g. Software Engineer Intern – Frontend", text: $title)

                            fieldLabel("Job ID", required: true)
                            borderedTextField("e.g. EPD-SWE-FE-INT-01", text: $code)

                            fieldLabel("Department")
                            tappableField(department.isEmpty ? "Select a department" : department) { showDepartmentSheet = true }
                            Button {
                                showAddDepartment = true
                            } label: {
                                Label("Add Department", systemImage: "plus.circle.fill")
                                    .font(.system(size: 14, weight: .medium))
                                    .foregroundColor(AppTheme.primary)
                            }

                            fieldLabel("Location", required: true)
                            borderedTextField("Remote", text: $location)

                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: 6) {
                                    fieldLabel("Start date")
                                    tappableField(startDate.formatted(.dateTime.month(.abbreviated).day().year()), icon: "calendar") { showStartDateSheet = true }
                                }
                                VStack(alignment: .leading, spacing: 6) {
                                    fieldLabel("Start time")
                                    tappableField(startDate.formatted(.dateTime.hour().minute()), icon: "clock") { showStartTimeSheet = true }
                                }
                            }
                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: 6) {
                                    fieldLabel("End date")
                                    tappableField(endDate.formatted(.dateTime.month(.abbreviated).day().year()), icon: "calendar") { showEndDateSheet = true }
                                }
                                VStack(alignment: .leading, spacing: 6) {
                                    fieldLabel("End time")
                                    tappableField(endDate.formatted(.dateTime.hour().minute()), icon: "clock") { showEndTimeSheet = true }
                                }
                            }

                            fieldLabel("Employment Type", required: true)
                            tappableField(employmentType.rawValue) { showEmploymentSheet = true }

                            fieldLabel("Work Arrangement")
                            tappableField(workArrangement.rawValue) { showArrangementSheet = true }
                        }

                        card {
                            Text("Salary Range").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                            borderedTextField("e.g. $80,000–$120,000", text: $salaryRange)
                        }

                        card {
                            Text("Role Description").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                            TextEditor(text: $description)
                                .frame(minHeight: 100)
                                .padding(8)
                                .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.divider, lineWidth: 1))
                        }

                        card {
                            Text("Assessment").font(.system(size: 15, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                            fieldLabel("Number of questions")
                            tappableField("\(numberOfQuestions) question\(numberOfQuestions == 1 ? "" : "s")") { showQuestionCountSheet = true }
                        }

                        if let err = saveError {
                            Text(err).foregroundColor(AppTheme.danger).font(.caption)
                        }
                    }
                    .padding(16)
                    .padding(.bottom, 80)
                }

                HStack(spacing: 12) {
                    Button("Save as Draft") { save(status: "draft") }
                        .frame(maxWidth: .infinity).frame(height: 48)
                        .background(AppTheme.secondaryBackground)
                        .foregroundColor(AppTheme.textPrimary)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                    Button("Publish Job") { showPublishConfirm = true }
                        .frame(maxWidth: .infinity).frame(height: 48)
                        .background(AppTheme.primary)
                        .foregroundColor(.white)
                        .cornerRadius(AppTheme.buttonCornerRadius)
                }
                .font(.system(size: 15, weight: .semibold))
                .padding(.horizontal, 16).padding(.vertical, 12)
                .background(.regularMaterial)
                .overlay(isSaving ? ProgressView().scaleEffect(0.9) : nil)
            }
            .background(AppTheme.groupedBackground.ignoresSafeArea())
            .navigationTitle(isNew ? "Add Job Posting" : "Edit Job")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Text(isNew ? "New" : "Draft")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(AppTheme.warning)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(AppTheme.warning.opacity(0.15))
                        .cornerRadius(20)
                }
            }
            .confirmationDialog("Publish this job?", isPresented: $showPublishConfirm) {
                Button("Publish") { save(status: "open") }
                Button("Cancel", role: .cancel) {}
            }
            .task { await loadDepartments() }
            .alert("New Department", isPresented: $showAddDepartment) {
                TextField("Department name", text: $newDepartmentName)
                Button("Add") { Task { await addDepartment() } }
                    .disabled(newDepartmentName.trimmingCharacters(in: .whitespaces).isEmpty)
                Button("Cancel", role: .cancel) { newDepartmentName = "" }
            }
            .alert("Couldn't add department", isPresented: Binding(
                get: { departmentError != nil },
                set: { if !$0 { departmentError = nil } }
            )) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(departmentError ?? "")
            }
            .sheet(isPresented: $showDepartmentSheet) {
                DepartmentSelectSheet(selection: $department, departments: availableDepartments) {
                    showDepartmentSheet = false
                    showAddDepartment = true
                }
            }
            .sheet(isPresented: $showEmploymentSheet) {
                SelectionListSheet(title: "Employment type", options: EmploymentType.allCases, selection: $employmentType) { $0.rawValue }
            }
            .sheet(isPresented: $showArrangementSheet) {
                SelectionListSheet(title: "Work arrangement", options: WorkArrangement.allCases, selection: $workArrangement) { $0.rawValue }
            }
            .sheet(isPresented: $showStartDateSheet) {
                DateSheet(title: "Start date", date: $startDate)
            }
            .sheet(isPresented: $showEndDateSheet) {
                DateSheet(title: "End date", date: $endDate)
            }
            .sheet(isPresented: $showStartTimeSheet) {
                TimeSheet(title: "Start time", date: $startDate)
            }
            .sheet(isPresented: $showEndTimeSheet) {
                TimeSheet(title: "End time", date: $endDate)
            }
            .sheet(isPresented: $showQuestionCountSheet) {
                SelectionListSheet(title: "Number of questions", options: [1, 2, 3, 4, 5], selection: $numberOfQuestions) { "\($0) question\($0 == 1 ? "" : "s")" }
            }
        }
    }

    @ViewBuilder
    private func card<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            content()
        }
        .padding(16)
        .background(AppTheme.background)
        .cornerRadius(AppTheme.cardCornerRadius)
        .shadow(color: AppTheme.cardShadow, radius: 8, x: 0, y: 2)
    }

    private func fieldLabel(_ text: String, required: Bool = false) -> some View {
        HStack(spacing: 2) {
            Text(text).font(.system(size: 13, weight: .medium)).foregroundColor(AppTheme.textPrimary)
            if required { Text("*").foregroundColor(AppTheme.danger) }
        }
        .padding(.top, 4)
    }

    private func borderedTextField(_ placeholder: String, text: Binding<String>) -> some View {
        TextField(placeholder, text: text)
            .padding(.horizontal, 14).padding(.vertical, 12)
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.divider, lineWidth: 1))
    }

    private func tappableField(_ text: String, icon: String = "chevron.down", action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(text).font(.system(size: 15)).foregroundColor(AppTheme.textPrimary)
                Spacer()
                Image(systemName: icon).font(.system(size: 13)).foregroundColor(AppTheme.textSecondary)
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(AppTheme.divider, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func loadDepartments() async {
        availableDepartments = (try? await api.fetchDepartments()) ?? []
    }

    private func addDepartment() async {
        let name = newDepartmentName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return }
        newDepartmentName = ""
        do {
            let dept = try await api.createDepartment(name: name)
            availableDepartments.append(dept)
            department = dept.name
        } catch {
            departmentError = error.localizedDescription
        }
    }

    private func save(status: String) {
        guard !title.isEmpty, !code.isEmpty else {
            saveError = "Title and Job ID are required."
            return
        }
        isSaving = true
        saveError = nil
        let body: [String: Any] = [
            "title": title, "code": code, "department": department,
            "location": location,
            "employment_type": employmentType.rawValue,
            "work_arrangement": workArrangement.rawValue,
            "salary_range": salaryRange,
            "description": description,
            "question_count": numberOfQuestions,
            "status": status,
        ]
        Task { @MainActor in
            defer { isSaving = false }
            do {
                if let existing = job {
                    _ = try await api.updateJob(code: existing.jobId, body: body)
                } else {
                    _ = try await api.createJob(body)
                }
                onSave?(job, status)
                dismiss()
            } catch {
                saveError = error.localizedDescription
            }
        }
    }
}

// MARK: – Selection sheets

struct SelectionListSheet<T: Hashable>: View {
    let title: String
    let options: [T]
    @Binding var selection: T
    let label: (T) -> String
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title).font(.system(size: 18, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 12)
            ForEach(options, id: \.self) { option in
                Button {
                    selection = option
                    dismiss()
                } label: {
                    HStack {
                        Text(label(option))
                            .font(.system(size: 16))
                            .foregroundColor(option == selection ? AppTheme.primary : AppTheme.textPrimary)
                        Spacer()
                        if option == selection {
                            Image(systemName: "checkmark").foregroundColor(AppTheme.primary)
                        }
                    }
                    .padding(.horizontal, 20).padding(.vertical, 14)
                    .background(option == selection ? AppTheme.primaryLight : Color.clear)
                }
                .buttonStyle(.plain)
            }
            Spacer(minLength: 8)
        }
        .padding(.bottom, 16)
        .presentationDetents([.medium])
    }
}

struct DepartmentSelectSheet: View {
    @Binding var selection: String
    let departments: [APIDepartment]
    var onAddNew: () -> Void
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Select department").font(.system(size: 18, weight: .bold)).foregroundColor(AppTheme.textPrimary)
                .padding(.horizontal, 20).padding(.top, 8).padding(.bottom, 12)
            ForEach(departments, id: \.id) { dept in
                Button {
                    selection = dept.name
                    dismiss()
                } label: {
                    HStack {
                        Text(dept.name)
                            .font(.system(size: 16))
                            .foregroundColor(dept.name == selection ? AppTheme.primary : AppTheme.textPrimary)
                        Spacer()
                        if dept.name == selection {
                            Image(systemName: "checkmark").foregroundColor(AppTheme.primary)
                        }
                    }
                    .padding(.horizontal, 20).padding(.vertical, 14)
                    .background(dept.name == selection ? AppTheme.primaryLight : Color.clear)
                }
                .buttonStyle(.plain)
            }
            Button(action: onAddNew) {
                Label("Add department", systemImage: "plus")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundColor(AppTheme.primary)
                    .padding(.horizontal, 20).padding(.vertical, 14)
            }
            Spacer(minLength: 8)
        }
        .padding(.bottom, 16)
        .presentationDetents([.medium])
    }
}

struct DateSheet: View {
    let title: String
    @Binding var date: Date
    @State private var draft: Date = Date()
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(spacing: 16) {
            DatePicker(title, selection: $draft, displayedComponents: .date)
                .datePickerStyle(.graphical)
                .labelsHidden()
                .padding(.horizontal, 16)
            Button("Confirm date") {
                date = draft
                dismiss()
            }
            .frame(maxWidth: .infinity).frame(height: 48)
            .background(AppTheme.primary).foregroundColor(.white)
            .cornerRadius(AppTheme.buttonCornerRadius)
            .font(.system(size: 15, weight: .semibold))
            .padding(.horizontal, 16)
        }
        .padding(.top, 8).padding(.bottom, 16)
        .onAppear { draft = date }
        .presentationDetents([.large])
    }
}

struct TimeSheet: View {
    let title: String
    @Binding var date: Date
    @State private var draft: Date = Date()
    @Environment(\.dismiss) var dismiss

    var body: some View {
        VStack(spacing: 16) {
            Text(title).font(.system(size: 16, weight: .semibold)).foregroundColor(AppTheme.textPrimary)
            DatePicker(title, selection: $draft, displayedComponents: .hourAndMinute)
                .datePickerStyle(.wheel)
                .labelsHidden()
            Button("Confirm time") {
                date = draft
                dismiss()
            }
            .frame(maxWidth: .infinity).frame(height: 48)
            .background(AppTheme.primary).foregroundColor(.white)
            .cornerRadius(AppTheme.buttonCornerRadius)
            .font(.system(size: 15, weight: .semibold))
            .padding(.horizontal, 16)
        }
        .padding(.top, 16).padding(.bottom, 16)
        .onAppear { draft = date }
        .presentationDetents([.height(340)])
    }
}
