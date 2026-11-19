import axios from './axios-config';
import { getApiBaseUrl } from './baseUrl';
import { COURSE_SLUG } from './course';

/** Admin API for choosing the photos of the beginners course (staff only). */

import type { PhotoPick } from '../core/course-photo-roles';
import type { BackfillStatus, PlumageField, PlumageFields, PlumageFilter } from '../core/photo-plumage';

export type { PhotoPick };

export type CoursePhotoBird = {
  species_id: number;
  name: string;
  latin: string;
  plumage: string;
  file: { card: number[]; quiz: number[] };
  pick: PhotoPick | null;
};

export type CoursePhotoLesson = {
  week: number;
  title: string;
  kind?: string;
  birds: CoursePhotoBird[];
  /** Birds repeated from an earlier lesson: they show the photos chosen there. */
  reused?: { name: string; week: number }[];
};

export type CandidatePhoto = Partial<PlumageFields> & {
  id: number;
  url: string;
  thumb: string;
  link: string;
  contributor: string;
  license: string;
  source: string;
  approved: number;
  rejected: number;
};

/** The course being edited: `?course=uk-beginners` in the page address, else the Dutch course. */
export function photoCourseSlug(): string {
  try {
    const slug = new URLSearchParams(window.location.search).get('course');
    return slug && /^[a-z0-9-]+$/.test(slug) ? slug : COURSE_SLUG;
  } catch {
    return COURSE_SLUG;
  }
}

const base = () => `${getApiBaseUrl()}/api/courses/${photoCourseSlug()}/photos`;

export async function fetchCoursePhotos(): Promise<CoursePhotoLesson[]> {
  const res = await axios.get<{ lessons: CoursePhotoLesson[] }>(`${base()}/`);
  return res.data.lessons;
}

/** Visible photos of a species; `filter` is applied by the server (value `none` = not labelled). */
export async function fetchSpeciesPhotos(speciesId: number, filter: PlumageFilter = {}): Promise<CandidatePhoto[]> {
  const params = Object.fromEntries(Object.entries(filter).filter(([, v]) => !!v));
  const res = await axios.get<{ media: CandidatePhoto[] }>(`${base()}/species/${speciesId}/`, { params });
  return res.data.media;
}

/**
 * Confirm (no fields) or correct (the fields to change; '' clears one) the plumage of a photo.
 * The label becomes a human label with confidence 1, which nothing overwrites.
 */
export async function savePhotoPlumage(
  mediaId: number,
  fields: Partial<Record<PlumageField, string>> = {}
): Promise<PlumageFields> {
  const res = await axios.put<PlumageFields>(`${base()}/media/${mediaId}/plumage/`, fields);
  return res.data;
}

export async function savePhotoPick(week: number, speciesId: number, pick: PhotoPick): Promise<PhotoPick> {
  const res = await axios.put<PhotoPick>(`${base()}/${week}/${speciesId}/`, pick);
  return res.data;
}

/** The pick a bird starts from: the saved one, else the photos in the lesson file. */
export function startingPick(bird: CoursePhotoBird): PhotoPick {
  return bird.pick ?? { card: [...bird.file.card], quiz: [...bird.file.quiz], reject: [], done: false };
}

/** Add a Wikimedia Commons photo (page or file link) to the species; returns it as a candidate. */
export async function addCommonsPhoto(speciesId: number, link: string): Promise<CandidatePhoto> {
  try {
    const res = await axios.post<{ photo: CandidatePhoto }>(`${base()}/species/${speciesId}/commons/`, { link });
    return res.data.photo;
  } catch (error: any) {
    throw new Error(error?.response?.data?.error || 'De foto kon niet worden toegevoegd.');
  }
}

export async function fetchPlumageBackfill(): Promise<BackfillStatus> {
  return (await axios.get<BackfillStatus>(`${base()}/plumage-backfill/`)).data;
}

/**
 * Start the plumage backfill of the course's photos (iNaturalist, GBIF and Commons lookups).
 * One run at a time, and a cooldown between real runs: when refused, the current status comes back
 * with an `error` text instead of throwing.
 */
export async function startPlumageBackfill(options: { approved?: boolean; dry_run?: boolean }): Promise<BackfillStatus> {
  try {
    return (await axios.post<BackfillStatus>(`${base()}/plumage-backfill/`, options)).data;
  } catch (error: any) {
    const data = error?.response?.data;
    if (data && (error.response.status === 409 || error.response.status === 429)) return data;
    throw error;
  }
}
