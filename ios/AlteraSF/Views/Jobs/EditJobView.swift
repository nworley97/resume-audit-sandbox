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
            Form {
                Section("Basic Information") {
                    LabeledContent("Job Title") {
                        TextField("e.g. Software Engineer", text: $title).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Job ID / Code") {
                        TextField("e.g. EPD-001", text: $code).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Department") {
                        TextField("e.g. Engineering", text: $department).multilineTextAlignment(.trailing)
                    }
                    LabeledContent("Location") {
                        TextField("Remote", text: $location).multilineTextAlignment(.trailing)
                    }
                }
                Section("Schedule") {
                    DatePicker("Start date", selection: $startDate, displayedComponents: [.date, .hourAndMinute])
                    DatePicker("End date", selection: $endDate, displayedComponents: [.date, .hourAndMinute])
                }
                Section("Role Details") {
                    Picker("Employment Type", selection: $employmentType) {
                        ForEach(EmploymentType.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    Picker("Work Arrangement", selection: $workArrangement) {
                        ForEach(WorkArrangement.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                }
                Section("Salary Range") {
                    TextField("e.g. $80,000–$120,000", text: $salaryRange)
                }
                Section("Role Description") {
                    TextEditor(text: $description).frame(minHeight: 100)
                }
                Section("Assessment") {
                    Stepper("Questions: \(numberOfQuestions)", value: $numberOfQuestions, in: 1...5)
                }
                if let err = saveError {
                    Section {
                        Text(err).foregroundColor(AppTheme.danger).font(.caption)
                    }
                }
            }
            .navigationTitle(isNew ? "Create Job" : "Edit Job")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItemGroup(placement: .confirmationAction) {
                    if isSaving {
                        ProgressView().scaleEffect(0.8)
                    } else {
                        Button("Save Draft") { save(status: "draft") }
                            .foregroundColor(AppTheme.textSecondary)
                        Button("Publish") { showPublishConfirm = true }
                            .fontWeight(.semibold).foregroundColor(AppTheme.primary)
                    }
                }
            }
            .confirmationDialog("Publish this job?", isPresented: $showPublishConfirm) {
                Button("Publish") { save(status: "open") }
                Button("Cancel", role: .cancel) {}
            }
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
