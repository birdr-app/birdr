import axios from './axios-config';
import { getApiBaseUrl } from './baseUrl';
import { COURSE_SLUG } from './course';

/** Admin API for choosing the photos of the beginners course (staff only). */

import type { PhotoPick } from '../core/course-photo-roles';

export type { PhotoPick };

export type CoursePhotoBird = {
  species_id: number;
  name: string;
  latin: string;
  plumage: string;
  file: { card: number[]; quiz: number[] };
  pick: PhotoPick | null;
};

export type CoursePhotoLesson = { week: number; title: string; birds: CoursePhotoBird[] };

export type CandidatePhoto = {
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

const base = () => `${getApiBaseUrl()}/api/courses/${COURSE_SLUG}/photos`;

export async function fetchCoursePhotos(): Promise<CoursePhotoLesson[]> {
  const res = await axios.get<{ lessons: CoursePhotoLesson[] }>(`${base()}/`);
  return res.data.lessons;
}

export async function fetchSpeciesPhotos(speciesId: number): Promise<CandidatePhoto[]> {
  const res = await axios.get<{ media: CandidatePhoto[] }>(`${base()}/species/${speciesId}/`);
  return res.data.media;
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
