<script lang="ts">
  import AnnotationProvider from "../AnnotationProvider.svelte";
</script>

<AnnotationProvider
  mode="owner"
  enabled
  editable={false}
  jobId="job-1"
  surfaceKey="selection:workspace:compare"
>
  <p>Saved decision content</p>
</AnnotationProvider>
