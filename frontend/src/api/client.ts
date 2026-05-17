import axios from 'axios'
import type { GenerationParams, JobStatus, UploadResponse, JobSubmitResponse } from '../types'

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
})

/**
 * Upload a GPX or IGC file to the server.
 * Returns upload_id and original filename.
 */
export async function uploadGPX(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await http.post<UploadResponse>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Submit a generation job with the given upload_id and parameters.
 * Returns the job_id for polling / SSE.
 */
export async function submitJob(
  uploadId: string,
  params: Partial<GenerationParams>,
): Promise<JobSubmitResponse> {
  const { data } = await http.post<JobSubmitResponse>('/api/jobs', {
    upload_id: uploadId,
    params,
  })
  return data
}

/**
 * Fetch current status of a job (polling fallback).
 */
export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const { data } = await http.get<JobStatus>(`/api/jobs/${jobId}`)
  return data
}

/**
 * Request cancellation of a running job.
 */
export async function cancelJob(jobId: string): Promise<void> {
  await http.delete(`/api/jobs/${jobId}`)
}

/**
 * Build a download URL for a job output file.
 */
export function getFileUrl(jobId: string, filename: string): string {
  return `${BASE_URL}/api/jobs/${jobId}/files/${encodeURIComponent(filename)}`
}

/**
 * Build the SSE stream URL for a job.
 */
export function getStreamUrl(jobId: string): string {
  return `${BASE_URL}/api/jobs/${jobId}/stream`
}
