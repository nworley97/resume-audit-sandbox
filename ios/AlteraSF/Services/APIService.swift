import Foundation

enum APIError: Error, LocalizedError {
    case notAuthenticated
    case httpError(Int, String)
    case decodingError(Error)
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .notAuthenticated: return "Please sign in again."
        case .httpError(_, let msg): return msg
        case .decodingError: return "Invalid response from server."
        case .networkError(let e): return e.localizedDescription
        }
    }
}

enum ChangePlanOutcome {
    case applied(tier: String, cycle: String)
    case paymentRequired(URL)
}

final class APIService: ObservableObject {
    static let shared = APIService()

    private let base = AppConfig.baseURL
    private let session: URLSession

    // Published so views can react when auth is lost
    @Published var tenantSlug: String? = nil
    @Published var currentUser: APIUser? = nil

    init() {
        let config = URLSessionConfiguration.default
        config.httpCookieAcceptPolicy = .always
        config.httpShouldSetCookies = true
        config.httpCookieStorage = HTTPCookieStorage.shared
        self.session = URLSession(configuration: config)
    }

    // MARK: – Auth

    func login(email: String, password: String) async throws -> APIUser {
        let body: [String: String] = ["username": email, "password": password]
        let response: APILoginResponse = try await post("/api/mobile/auth/login", body: body)
        await MainActor.run {
            self.tenantSlug = response.user.tenantSlug
            self.currentUser = response.user
        }
        return response.user
    }

    func googleSignIn(idToken: String) async throws -> APIUser {
        let body: [String: String] = ["id_token": idToken]
        let response: APILoginResponse = try await post("/api/mobile/auth/google", body: body)
        await MainActor.run {
            self.tenantSlug = response.user.tenantSlug
            self.currentUser = response.user
        }
        return response.user
    }

    func logout() async throws {
        let _: EmptyResponse = try await post("/api/mobile/auth/logout", body: EmptyBody())
        await MainActor.run {
            self.tenantSlug = nil
            self.currentUser = nil
        }
    }

    func fetchMe() async throws -> APIUser {
        let user: APIUser = try await get("/api/mobile/auth/me")
        await MainActor.run {
            self.tenantSlug = user.tenantSlug
            self.currentUser = user
        }
        return user
    }

    func forgotPassword(email: String) async throws {
        let _: EmptyResponse = try await post("/api/mobile/auth/forgot-password", body: ["email": email])
    }

    // MARK: – Jobs

    func fetchJobs(status: String? = nil) async throws -> [APIJob] {
        let tenant = try requireTenant()
        var path = "/api/mobile/\(tenant)/jobs"
        if let s = status { path += "?status=\(s)" }
        return try await get(path)
    }

    func fetchJob(code: String) async throws -> APIJob {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/jobs/\(code)")
    }

    func createJob(_ body: [String: Any]) async throws -> APIJob {
        let tenant = try requireTenant()
        return try await postAny("/api/mobile/\(tenant)/jobs", body: body)
    }

    func updateJob(code: String, body: [String: Any]) async throws -> APIJob {
        let tenant = try requireTenant()
        return try await patchAny("/api/mobile/\(tenant)/jobs/\(code)", body: body)
    }

    func deleteJob(code: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await delete("/api/mobile/\(tenant)/jobs/\(code)")
    }

    func closeJob(code: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await post("/api/mobile/\(tenant)/jobs/\(code)/close", body: EmptyBody())
    }

    func reopenJob(code: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await post("/api/mobile/\(tenant)/jobs/\(code)/reopen", body: EmptyBody())
    }

    // MARK: – Departments

    func fetchDepartments() async throws -> [APIDepartment] {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/departments")
    }

    func createDepartment(name: String) async throws -> APIDepartment {
        let tenant = try requireTenant()
        return try await post("/api/mobile/\(tenant)/departments", body: ["name": name])
    }

    func deleteDepartment(id: Int) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await delete("/api/mobile/\(tenant)/departments/\(id)")
    }

    func updateDepartment(id: Int, name: String) async throws -> APIDepartment {
        let tenant = try requireTenant()
        return try await patchAny("/api/mobile/\(tenant)/departments/\(id)", body: ["name": name])
    }

    // MARK: – Candidates

    func fetchCandidates(jobCode: String? = nil, search: String? = nil,
                         sort: String = "score", page: Int = 1) async throws -> APICandidateListResponse {
        let tenant = try requireTenant()
        var comps = URLComponents()
        comps.queryItems = [URLQueryItem(name: "page", value: "\(page)")]
        if let jc = jobCode { comps.queryItems!.append(.init(name: "job_code", value: jc)) }
        if let s = search, !s.isEmpty { comps.queryItems!.append(.init(name: "q", value: s)) }
        comps.queryItems!.append(.init(name: "sort", value: sort))
        let qs = comps.percentEncodedQuery.map { "?\($0)" } ?? ""
        return try await get("/api/mobile/\(tenant)/candidates\(qs)")
    }

    func fetchCandidate(id: String) async throws -> APICandidate {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/candidates/\(id)")
    }

    func setCandidateStatus(id: String, status: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await patch(
            "/api/mobile/\(tenant)/candidates/\(id)/status",
            body: ["status": status]
        )
    }

    // MARK: – Profile & Password

    func updateProfile(fullName: String, email: String, company: String) async throws -> APIProfile {
        try await patch("/api/mobile/auth/profile", body: ["full_name": fullName, "email": email, "company": company])
    }

    func changePassword(current: String, new: String) async throws {
        let _: EmptyResponse = try await post("/api/mobile/auth/change-password", body: ["current_password": current, "new_password": new])
    }

    // MARK: – Team

    func fetchTeam() async throws -> [APITeamMember] {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/team")
    }

    func inviteTeamMember(name: String, email: String, role: String) async throws -> APITeamMember {
        let tenant = try requireTenant()
        return try await post("/api/mobile/\(tenant)/team/invite", body: ["name": name, "email": email, "role": role])
    }

    func updateTeamMemberRole(id: Int, role: String) async throws -> APITeamMember {
        let tenant = try requireTenant()
        return try await patch("/api/mobile/\(tenant)/team/\(id)", body: ["role": role])
    }

    func removeTeamMember(id: Int) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await delete("/api/mobile/\(tenant)/team/\(id)")
    }

    // MARK: – Notifications

    func fetchNotifications() async throws -> [APINotification] {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/notifications")
    }

    func markAllNotificationsRead() async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await post("/api/mobile/\(tenant)/notifications/read-all", body: EmptyBody())
    }

    func markNotificationRead(id: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await patch("/api/mobile/\(tenant)/notifications/\(id)/read", body: EmptyBody())
    }

    // MARK: – Billing

    func fetchBilling() async throws -> APIBillingResponse {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/billing")
    }

    func changePlan(tier: String, cycle: String) async throws -> ChangePlanOutcome {
        let tenant = try requireTenant()
        let data = try JSONEncoder().encode(["plan_tier": tier, "billing_cycle": cycle])
        let req = request(path: "/api/mobile/\(tenant)/billing/change-plan", method: "POST", body: data)
        let (responseData, response): (Data, URLResponse)
        do {
            (responseData, response) = try await session.data(for: req)
        } catch {
            throw APIError.networkError(error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.networkError(URLError(.badServerResponse))
        }
        if http.statusCode == 402 {
            guard let parsed = try? JSONDecoder().decode(APIChangePlanResponse.self, from: responseData),
                  let urlString = parsed.paymentUrl,
                  let url = URL(string: urlString) else {
                throw APIError.httpError(402, "Payment required to change plan.")
            }
            return .paymentRequired(url)
        }
        guard (200...299).contains(http.statusCode) else {
            let raw = (try? JSONDecoder().decode(APIErrorResponse.self, from: responseData))?.text
                ?? String(data: responseData, encoding: .utf8)
                ?? "Server error"
            if http.statusCode == 401 { throw APIError.notAuthenticated }
            throw APIError.httpError(http.statusCode, Self.cleanErrorMessage(raw, statusCode: http.statusCode))
        }
        let parsed = try? JSONDecoder().decode(APIChangePlanResponse.self, from: responseData)
        return .applied(tier: parsed?.planTier ?? tier, cycle: parsed?.billingCycle ?? cycle)
    }

    func cancelSubscription() async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await post("/api/mobile/\(tenant)/billing/cancel", body: EmptyBody())
    }

    func fetchBillingPortalURL() async throws -> String {
        let tenant = try requireTenant()
        let response: APIPortalResponse = try await get("/api/mobile/\(tenant)/billing/portal")
        return response.url
    }

    // MARK: – Resume download (authenticated, returns raw bytes + suggested filename)

    func fetchResumeData(candidateId: String) async throws -> (Data, String) {
        let tenant = try requireTenant()
        let req = request(path: "/api/mobile/\(tenant)/candidates/\(candidateId)/resume", method: "GET", body: nil)
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw APIError.networkError(error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.networkError(URLError(.badServerResponse))
        }
        guard (200...299).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.notAuthenticated }
            throw APIError.httpError(http.statusCode, "Unable to download resume")
        }
        let filename = response.suggestedFilename ?? "resume.pdf"
        return (data, filename)
    }

    // MARK: – Analytics

    func fetchAnalyticsOverview() async throws -> APIAnalyticsOverview {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/analytics")
    }

    func fetchJobAnalytics(code: String) async throws -> APIJobAnalyticsDetail {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/analytics/\(code)")
    }

    func fetchFinalistCandidateOptions(jobCode: String) async throws -> [APIFinalistCandidateOption] {
        let tenant = try requireTenant()
        return try await get("/api/mobile/\(tenant)/analytics/\(jobCode)/candidates")
    }

    func setCandidateNote(id: String, note: String) async throws {
        let tenant = try requireTenant()
        let _: EmptyResponse = try await patch(
            "/api/mobile/\(tenant)/candidates/\(id)/note",
            body: ["note": note]
        )
    }

    // MARK: – Private networking

    private func requireTenant() throws -> String {
        guard let t = tenantSlug else { throw APIError.notAuthenticated }
        return t
    }

    private func request(path: String, method: String, body: Data?) -> URLRequest {
        var req = URLRequest(url: URL(string: base.absoluteString + path)!)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.httpBody = body
        return req
    }

    private func perform<T: Decodable>(_ req: URLRequest) async throws -> T {
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw APIError.networkError(error)
        }
        guard let http = response as? HTTPURLResponse else {
            throw APIError.networkError(URLError(.badServerResponse))
        }
        guard (200...299).contains(http.statusCode) else {
            let rawMsg = (try? JSONDecoder().decode(APIErrorResponse.self, from: data))?.text
                ?? String(data: data, encoding: .utf8)
                ?? "Server error"
            let msg = Self.cleanErrorMessage(rawMsg, statusCode: http.statusCode)
            if http.statusCode == 401 { throw APIError.notAuthenticated }
            throw APIError.httpError(http.statusCode, msg)
        }
        // EmptyResponse special case
        if T.self == EmptyResponse.self {
            return EmptyResponse() as! T
        }
        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }

    /// Guards against ever surfacing a raw HTML error page (e.g. an un-caught
    /// Flask/werkzeug error page) in the UI — falls back to a short, clean message.
    private static func cleanErrorMessage(_ raw: String, statusCode: Int) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let looksLikeHTML = trimmed.hasPrefix("<!DOCTYPE") || trimmed.hasPrefix("<html") || trimmed.contains("</html>")
        if looksLikeHTML || trimmed.isEmpty {
            return "Something went wrong. Please try again."
        }
        return trimmed
    }

    func get<T: Decodable>(_ path: String) async throws -> T {
        try await perform(request(path: path, method: "GET", body: nil))
    }

    func post<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        let data = try JSONEncoder().encode(body)
        return try await perform(request(path: path, method: "POST", body: data))
    }

    func patch<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        let data = try JSONEncoder().encode(body)
        return try await perform(request(path: path, method: "PATCH", body: data))
    }

    func delete<T: Decodable>(_ path: String) async throws -> T {
        try await perform(request(path: path, method: "DELETE", body: nil))
    }

    // Any-typed body variants (for [String: Any] dicts)
    func postAny<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        let data = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request(path: path, method: "POST", body: data))
    }

    func patchAny<T: Decodable>(_ path: String, body: [String: Any]) async throws -> T {
        let data = try JSONSerialization.data(withJSONObject: body)
        return try await perform(request(path: path, method: "PATCH", body: data))
    }
}

private struct EmptyBody: Encodable {}
private struct EmptyResponse: Decodable {}
