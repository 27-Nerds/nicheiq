<script lang="ts">
  import { page } from '$app/stores';
  import {
    Plus,
    FileText,
    Clock,
    CheckCircle,
    XCircle,
    Loader2,
    ArrowRight,
    Search,
    BarChart3
  } from 'lucide-svelte';

  interface Job {
    id: string;
    email: string;
    niche: string;
    status: string;
    progress: number;
    createdAt: string;
    updatedAt: string;
    errorMessage?: string;
    userId?: string;
  }

  let { data } = $props();

  const session = $derived($page.data.session);
  const jobs = $derived(data.jobs as Job[]);

  function getStatusBadge(status: string) {
    switch (status.toUpperCase()) {
      case 'COMPLETED':
        return { class: 'badge-success', icon: CheckCircle, text: 'Completed' };
      case 'RUNNING':
        return { class: 'badge-warning', icon: Loader2, text: 'Running' };
      case 'PENDING':
        return { class: 'badge-muted', icon: Clock, text: 'Pending' };
      case 'FAILED':
        return { class: 'badge-error', icon: XCircle, text: 'Failed' };
      default:
        return { class: 'badge-muted', icon: Clock, text: status };
    }
  }

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
</script>

<svelte:head>
  <title>Dashboard - NicheIQ</title>
</svelte:head>

<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
    <div>
      <h1 class="text-2xl font-bold text-text-primary">
        Welcome back{session?.user?.name ? `, ${session.user.name}` : ''}
      </h1>
      <p class="text-text-muted mt-1">
        Manage your market research reports
      </p>
    </div>
    <a href="/jobs/new" class="btn-primary">
      <Plus class="w-4 h-4" />
      New Research
    </a>
  </div>

  <!-- Stats Overview -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
    <div class="card">
      <div class="flex items-center gap-3">
        <div class="icon-container">
          <FileText class="w-5 h-5 text-accent" />
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">{jobs.length}</p>
          <p class="text-sm text-text-muted">Total Reports</p>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="flex items-center gap-3">
        <div class="icon-container-success">
          <CheckCircle class="w-5 h-5 text-success" />
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">
            {jobs.filter((j) => j.status.toUpperCase() === 'COMPLETED').length}
          </p>
          <p class="text-sm text-text-muted">Completed</p>
        </div>
      </div>
    </div>
    <div class="card">
      <div class="flex items-center gap-3">
        <div class="p-2.5 rounded-lg bg-warning/10 border border-warning/20">
          <Loader2 class="w-5 h-5 text-warning" />
        </div>
        <div>
          <p class="text-2xl font-bold text-text-primary">
            {jobs.filter((j) => j.status.toUpperCase() === 'RUNNING' || j.status.toUpperCase() === 'PENDING').length}
          </p>
          <p class="text-sm text-text-muted">In Progress</p>
        </div>
      </div>
    </div>
  </div>

  <!-- Job List -->
  {#if jobs.length === 0}
    <div class="card text-center py-16">
      <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-accent/10 flex items-center justify-center">
        <Search class="w-8 h-8 text-accent" />
      </div>
      <h2 class="text-xl font-semibold text-text-primary mb-2">
        No research yet
      </h2>
      <p class="text-text-muted mb-6 max-w-md mx-auto">
        Start your first market research to validate a SaaS idea and get actionable insights.
      </p>
      <a href="/jobs/new" class="btn-primary inline-flex">
        <Plus class="w-4 h-4" />
        Start Your First Research
      </a>
    </div>
  {:else}
    <div class="space-y-4">
      <h2 class="text-lg font-semibold text-text-primary flex items-center gap-2">
        <BarChart3 class="w-5 h-5 text-accent" />
        Your Research Reports
      </h2>

      <div class="grid gap-4">
        {#each jobs as job}
          {@const statusBadge = getStatusBadge(job.status)}
          {@const StatusIcon = statusBadge.icon}
          <div class="card hover:shadow-md transition-shadow">
            <div class="flex flex-col sm:flex-row sm:items-center gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-3 mb-2">
                  <h3 class="text-lg font-semibold text-text-primary truncate">
                    {job.niche}
                  </h3>
                  <span class="badge {statusBadge.class} flex items-center gap-1.5 shrink-0">
                    <StatusIcon class="w-3 h-3 {job.status.toUpperCase() === 'RUNNING' ? 'animate-spin' : ''}" />
                    {statusBadge.text}
                  </span>
                </div>
                <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-text-muted">
                  <span class="flex items-center gap-1">
                    <Clock class="w-3.5 h-3.5" />
                    {formatDate(job.createdAt)}
                  </span>
                  {#if job.status.toUpperCase() === 'RUNNING' && job.progress > 0}
                    <span>Progress: {job.progress}%</span>
                  {/if}
                  {#if job.errorMessage}
                    <span class="text-error">{job.errorMessage}</span>
                  {/if}
                </div>
              </div>

              <div class="flex items-center gap-2 shrink-0">
                {#if job.status.toUpperCase() === 'COMPLETED'}
                  <a
                    href="/jobs/{job.id}/report"
                    class="btn-primary"
                  >
                    View Report
                    <ArrowRight class="w-4 h-4" />
                  </a>
                {:else if job.status.toUpperCase() === 'RUNNING' || job.status.toUpperCase() === 'PENDING'}
                  <a
                    href="/jobs/{job.id}"
                    class="btn-secondary"
                  >
                    View Progress
                    <ArrowRight class="w-4 h-4" />
                  </a>
                {:else}
                  <a
                    href="/jobs/{job.id}"
                    class="btn-tertiary"
                  >
                    View Details
                  </a>
                {/if}
              </div>
            </div>

            {#if job.status.toUpperCase() === 'RUNNING' && job.progress > 0}
              <div class="mt-4">
                <div class="progress-bar">
                  <div
                    class="progress-bar-fill"
                    style="width: {job.progress}%"
                  ></div>
                </div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>
