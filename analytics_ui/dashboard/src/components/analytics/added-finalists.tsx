"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus, Star, X } from "lucide-react";
import {
  getAnalyticsJobCandidates,
  setCandidateFinalist,
  setCandidateNote,
} from "@/lib/api";
import type { AnalyticsFinalist, AnalyticsJobDetail } from "@/types/analytics";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";

function formatScore(value: number | null | undefined, digits = 1) {
  return Number.isFinite(value) ? (value as number).toFixed(digits) : "0.0";
}

const VISIBLE_ROWS = 5;

function NotePopover({
  finalist,
  tenant,
  jobCode,
}: {
  finalist: AnalyticsFinalist;
  tenant: string;
  jobCode: string;
}) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(finalist.note);
  const [open, setOpen] = useState(false);

  const mutation = useMutation({
    mutationFn: (note: string) => setCandidateNote(finalist.id, tenant, note),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analytics-detail", tenant, jobCode] });
      setOpen(false);
    },
  });

  return (
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setDraft(finalist.note);
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="h-7 px-2 text-xs cursor-pointer">
          {finalist.note ? "Edit Note" : "+ Note"}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 space-y-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={`Add a note about ${finalist.name}…`}
          rows={4}
          className="w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
        />
        <div className="flex justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            className="cursor-pointer"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            className="cursor-pointer"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(draft.trim())}
          >
            Save
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function AddCandidatesDialog({
  tenant,
  jobCode,
  open,
  onOpenChange,
}: {
  tenant: string;
  jobCode: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");

  const { data: candidates, isLoading } = useQuery({
    queryKey: ["analytics-job-candidates", tenant, jobCode],
    queryFn: () => getAnalyticsJobCandidates(jobCode, tenant),
    enabled: open,
  });

  const addMutation = useMutation({
    mutationFn: (cid: string) => setCandidateFinalist(cid, tenant, "add"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analytics-detail", tenant, jobCode] });
      queryClient.invalidateQueries({ queryKey: ["analytics-job-candidates", tenant, jobCode] });
    },
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return candidates ?? [];
    return (candidates ?? []).filter((c) => c.name.toLowerCase().includes(q));
  }, [candidates, search]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Candidates</DialogTitle>
          <DialogDescription>
            Shortlist candidates from this job&apos;s applicant pool to compare as finalists.
          </DialogDescription>
        </DialogHeader>
        <Input
          placeholder="Search candidates…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="max-h-80 space-y-1 overflow-y-auto">
          {isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Loading…</p>
          ) : filtered.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No remaining candidates to add.
            </p>
          ) : (
            filtered.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-md border border-border/60 px-3 py-2"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">{c.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Claim {formatScore(c.claim_validity_score)}/5 • Relevancy{" "}
                    {formatScore(c.relevancy_score)}/5
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="cursor-pointer"
                  disabled={addMutation.isPending}
                  onClick={() => addMutation.mutate(c.id)}
                >
                  <Plus className="size-4" />
                  Add
                </Button>
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function AddedFinalists({
  detail,
  tenant,
  jobCode,
}: {
  detail: AnalyticsJobDetail;
  tenant: string;
  jobCode: string;
}) {
  const queryClient = useQueryClient();
  const finalists = detail.finalists;
  const [showAll, setShowAll] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const removeMutation = useMutation({
    mutationFn: (cid: string) => setCandidateFinalist(cid, tenant, "remove"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["analytics-detail", tenant, jobCode] });
    },
  });

  const visible = showAll ? finalists : finalists.slice(0, VISIBLE_ROWS);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Added Finalists</h3>
          <p className="text-sm text-muted-foreground">
            Shortlisted candidates you&apos;re comparing for this role.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {finalists.length > VISIBLE_ROWS ? (
            <Button
              variant="link"
              size="sm"
              className="cursor-pointer px-0"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll ? "Show less" : "View all"}
            </Button>
          ) : null}
          <Button size="sm" className="cursor-pointer" onClick={() => setAddDialogOpen(true)}>
            <Plus className="size-4" />
            Add Candidates
          </Button>
        </div>
      </div>

      {finalists.length === 0 ? (
        <div className="rounded-lg border-dashed border-border/70 bg-muted/40 p-6 text-center">
          <Star className="mx-auto size-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground mt-2">
            No finalists added yet. Use &quot;Add Candidates&quot; to build your shortlist.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border/60">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border/60 bg-muted/40 text-xs text-muted-foreground">
                <th className="w-10 px-4 py-2 text-left font-medium">#</th>
                <th className="px-4 py-2 text-left font-medium">Candidate</th>
                <th className="px-4 py-2 text-left font-medium">Relevancy</th>
                <th className="px-4 py-2 text-left font-medium">Claim</th>
                <th className="px-4 py-2 text-left font-medium">AI/QA</th>
                <th className="px-4 py-2 text-left font-medium">Tabs</th>
                <th className="px-4 py-2 text-left font-medium">Overall</th>
                <th className="px-4 py-2 text-left font-medium">Note</th>
                <th className="w-10 px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {visible.map((finalist, idx) => (
                <tr key={finalist.id} className="border-b border-border/40 last:border-0">
                  <td className="px-4 py-3 text-muted-foreground">{idx + 1}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{finalist.name}</span>
                      {finalist.flagged ? (
                        <Badge
                          variant="destructive"
                          className="gap-1 text-[10px]"
                          title={finalist.flag_reason ?? undefined}
                        >
                          <AlertTriangle className="size-3" />
                          Flagged
                        </Badge>
                      ) : null}
                    </div>
                    {finalist.flagged && finalist.flag_reason ? (
                      <p className="text-xs text-destructive/80">{finalist.flag_reason}</p>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">{formatScore(finalist.relevancy_score)}/5</td>
                  <td className="px-4 py-3">{formatScore(finalist.claim_validity_score)}/5</td>
                  <td className="px-4 py-3">
                    {finalist.total_answers > 0
                      ? `${finalist.flagged_answers}/${finalist.total_answers}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3">{finalist.tab_switches}</td>
                  <td className="px-4 py-3 font-semibold text-foreground">
                    {formatScore(finalist.overall_score)}/5
                  </td>
                  <td className="px-4 py-3">
                    <NotePopover finalist={finalist} tenant={tenant} jobCode={jobCode} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 cursor-pointer text-muted-foreground hover:text-destructive"
                      disabled={removeMutation.isPending}
                      onClick={() => removeMutation.mutate(finalist.id)}
                      aria-label={`Remove ${finalist.name} from finalists`}
                    >
                      <X className="size-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AddCandidatesDialog
        tenant={tenant}
        jobCode={jobCode}
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
      />
    </div>
  );
}
