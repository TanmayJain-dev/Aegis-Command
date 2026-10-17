"use client";

import React, { useState, useRef } from "react";
import { Upload, X, Video, FileCode, CheckCircle, AlertCircle } from "lucide-react";
import { FeedManifestItem } from "../lib/feeds";

export interface UploadFeedModalProps {
  isOpen: boolean;
  onClose: () => void;
  onFeedCreated: (feed: FeedManifestItem) => void;
}

export function UploadFeedModal({
  isOpen,
  onClose,
  onFeedCreated,
}: UploadFeedModalProps) {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [feedLabel, setFeedLabel] = useState("");
  const [sensorType, setSensorType] = useState("EO/IR Optronics");
  const [lat, setLat] = useState("31.4520");
  const [lng, setLng] = useState("74.9250");
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const videoInputRef = useRef<HTMLInputElement | null>(null);
  const jsonInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const handleVideoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoFile(file);
      if (!feedLabel) {
        const cleanName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ").toUpperCase();
        setFeedLabel(cleanName.slice(0, 24));
      }
      setErrorMessage("");
    }
  };

  const handleJsonSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setJsonFile(file);
    }
  };

  const generateSyntheticDetections = (durationSec = 10) => {
    const timelineData: Record<string, Array<{
      id: string;
      class: string;
      confidence: number;
      box: [number, number, number, number];
      speed_kmh: number;
      direction: string;
    }>> = {};

    const steps = Math.min(Math.max(Math.floor(durationSec * 2), 6), 60);
    for (let i = 0; i < steps; i++) {
      const t = (i * 0.5).toFixed(2);
      const progress = i / steps;
      // Synthesize realistic tracked vehicles along an intersection trajectory
      const x1 = Math.round(600 + progress * 400);
      const y1 = Math.round(500 + Math.sin(progress * Math.PI) * 120);
      timelineData[t] = [
        {
          id: "Target-Track-1",
          class: "truck",
          confidence: 0.94,
          box: [x1, y1, x1 + 180, y1 + 120],
          speed_kmh: 38,
          direction: "NE",
        },
      ];
    }
    return timelineData;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) {
      setErrorMessage("Please select a valid video file (.mp4, .webm).");
      return;
    }

    setIsProcessing(true);
    setErrorMessage("");

    try {
      let detectionsData: Record<string, unknown>;

      if (jsonFile) {
        const text = await jsonFile.text();
        detectionsData = JSON.parse(text);
      } else {
        detectionsData = generateSyntheticDetections(15);
      }

      const videoObjectUrl = URL.createObjectURL(videoFile);
      const safeId = `feed-${videoFile.name.replace(/[^a-zA-Z0-9]/g, "-").toLowerCase()}-${videoFile.size}`;
      const newFeed: FeedManifestItem = {
        id: safeId,
        label: feedLabel.trim() || videoFile.name.slice(0, 20),
        video: videoObjectUrl,
        detections: detectionsData,
        center_lat: parseFloat(lat) || 31.452,
        center_lng: parseFloat(lng) || 74.925,
        sensor: sensorType,
      };

      onFeedCreated(newFeed);
      handleClose();
    } catch (err) {
      console.error("Feed creation error:", err);
      setErrorMessage("Failed to process companion detections JSON file.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClose = () => {
    setVideoFile(null);
    setJsonFile(null);
    setFeedLabel("");
    setErrorMessage("");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-3 sm:p-4 bg-black/85 backdrop-blur-sm">
      <div className="relative z-[10001] bg-slate-950 border border-cyan-500/40 rounded shadow-2xl w-full max-w-lg overflow-hidden flex flex-col font-mono">
        {/* Header */}
        <div className="bg-cyan-950/30 border-b border-cyan-500/30 px-4 py-3 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Upload size={16} className="text-cyan-400" />
            <span className="text-cyan-300 font-bold text-xs tracking-wider">
              AEGIS // IMPORT TACTICAL FEED
            </span>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="text-slate-400 hover:text-white transition-colors text-lg px-2"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-4 sm:p-5 flex flex-col gap-4 text-xs">
          {errorMessage && (
            <div className="p-2.5 bg-rose-950/60 border border-rose-500/50 rounded text-rose-300 flex items-center gap-2 text-[11px]">
              <AlertCircle size={14} className="flex-shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Video Selection */}
          <div className="flex flex-col gap-1.5">
            <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
              Surveillance Video File (.mp4, .webm) *
            </label>
            <div
              onClick={() => videoInputRef.current?.click()}
              className={`p-3 border border-dashed rounded cursor-pointer transition-colors flex items-center justify-between ${
                videoFile
                  ? "border-cyan-500/60 bg-cyan-950/20 text-cyan-300"
                  : "border-slate-700 bg-slate-900/40 text-slate-400 hover:border-slate-500 hover:bg-slate-900/80"
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <Video size={16} className={videoFile ? "text-cyan-400" : "text-slate-500"} />
                <span className="truncate">{videoFile ? videoFile.name : "Select video file from device..."}</span>
              </div>
              {videoFile && <CheckCircle size={14} className="text-cyan-400 flex-shrink-0" />}
            </div>
            <input
              ref={videoInputRef}
              type="file"
              accept="video/mp4,video/webm,video/quicktime"
              onChange={handleVideoSelect}
              className="hidden"
            />
          </div>

          {/* Optional Detections JSON */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Companion Detections JSON (Optional)
              </label>
              <span className="text-slate-600 text-[9px]">ByteTrack format</span>
            </div>
            <div
              onClick={() => jsonInputRef.current?.click()}
              className={`p-2.5 border border-dashed rounded cursor-pointer transition-colors flex items-center justify-between ${
                jsonFile
                  ? "border-emerald-500/60 bg-emerald-950/20 text-emerald-300"
                  : "border-slate-800 bg-slate-900/30 text-slate-500 hover:border-slate-600"
              }`}
            >
              <div className="flex items-center gap-2 truncate text-[11px]">
                <FileCode size={14} className={jsonFile ? "text-emerald-400" : "text-slate-600"} />
                <span className="truncate">
                  {jsonFile ? jsonFile.name : "Upload detections.json (or auto-synthesize)"}
                </span>
              </div>
              {jsonFile && <CheckCircle size={14} className="text-emerald-400 flex-shrink-0" />}
            </div>
            <input
              ref={jsonInputRef}
              type="file"
              accept="application/json,.json"
              onChange={handleJsonSelect}
              className="hidden"
            />
          </div>

          {/* Feed Label & Sensor */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Feed Call-Sign
              </label>
              <input
                type="text"
                value={feedLabel}
                onChange={(e) => setFeedLabel(e.target.value)}
                placeholder="E.g. UAV DELTA"
                className="bg-black border border-slate-700 rounded px-2.5 py-1.5 text-white outline-none focus:border-cyan-500 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Sensor Payload
              </label>
              <select
                value={sensorType}
                onChange={(e) => setSensorType(e.target.value)}
                className="bg-black border border-slate-700 rounded px-2.5 py-1.5 text-white outline-none focus:border-cyan-500 text-xs"
              >
                <option value="EO/IR Optronics">EO/IR Optronics</option>
                <option value="Fixed Optical 1080p">Fixed Optical 1080p</option>
                <option value="Tactical Bodycam">Tactical Bodycam</option>
                <option value="Thermal LWIR">Thermal LWIR</option>
                <option value="Commercial UAS 4K">Commercial UAS 4K</option>
              </select>
            </div>
          </div>

          {/* Coordinates */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Sector Latitude
              </label>
              <input
                type="text"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                placeholder="31.4520"
                className="bg-black border border-slate-700 rounded px-2.5 py-1.5 text-white outline-none focus:border-cyan-500 text-xs"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-slate-400 font-bold uppercase tracking-wider text-[10px]">
                Sector Longitude
              </label>
              <input
                type="text"
                value={lng}
                onChange={(e) => setLng(e.target.value)}
                placeholder="74.9250"
                className="bg-black border border-slate-700 rounded px-2.5 py-1.5 text-white outline-none focus:border-cyan-500 text-xs"
              />
            </div>
          </div>

          {/* Modal Actions */}
          <div className="mt-2 pt-3 border-t border-slate-800 flex justify-end gap-3">
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-1.5 border border-slate-700 text-slate-400 hover:bg-slate-900 rounded text-xs transition-colors"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isProcessing || !videoFile}
              className={`px-5 py-1.5 rounded text-xs font-bold transition-all flex items-center gap-1.5 ${
                isProcessing || !videoFile
                  ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                  : "bg-cyan-950 border border-cyan-500/60 text-cyan-300 hover:bg-cyan-900 shadow-[0_0_12px_rgba(6,182,212,0.2)]"
              }`}
            >
              <Upload size={13} />
              {isProcessing ? "PROCESSING..." : "INGEST FEED"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
