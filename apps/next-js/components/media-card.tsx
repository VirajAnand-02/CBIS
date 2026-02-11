import { FileImage, FileVideo, FileText, Music, File } from "lucide-react";
import { format } from "date-fns";
import Image from "next/image";
import { Blurhash } from "react-blurhash";
import { useState } from "react";

export type MediaType = "Image" | "Video" | "Document" | "Audio";

export interface MediaItem {
  id: number | string;
  name: string;
  type: MediaType;
  date: Date;
  size: string;
  blobId?: string;
  thumbnailUrl?: string;
  mimeType?: string;
  blurhash?: string;
  width?: number;
  height?: number;
}

interface MediaCardProps {
  item: MediaItem;
  onClick?: () => void;
}

export function getFileIcon(type: MediaType, className: string = "h-5 w-5") {
  const iconClass = className;
  
  switch (type) {
    case "Image":
      return <FileImage className={`${iconClass} text-blue-500`} />;
    case "Video":
      return <FileVideo className={`${iconClass} text-purple-500`} />;
    case "Document":
      return <FileText className={`${iconClass} text-orange-500`} />;
    case "Audio":
      return <Music className={`${iconClass} text-green-500`} />;
    default:
      return <File className={`${iconClass} text-gray-500`} />;
  }
}

export function MediaCard({ item, onClick }: MediaCardProps) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const showThumbnail = item.thumbnailUrl || (item.blobId && item.type === "Image");
  const thumbnailSrc = item.thumbnailUrl || (item.blobId ? `/api/blobs/${item.blobId}/thumbnail` : null);

  return (
    <div
      onClick={onClick}
      className="group relative aspect-square rounded-lg overflow-hidden bg-muted hover:ring-2 hover:ring-primary transition-all cursor-pointer"
    >
      {showThumbnail && thumbnailSrc ? (
        <>
          {/* Blurhash placeholder */}
          {item.blurhash && !imageLoaded && (
            <div className="absolute inset-0">
              <Blurhash
                hash={item.blurhash}
                width="100%"
                height="100%"
                resolutionX={32}
                resolutionY={32}
                punch={1}
              />
            </div>
          )}
          
          <Image
            src={thumbnailSrc}
            alt={item.name}
            fill
            className={`object-cover transition-opacity duration-300 ${
              imageLoaded ? "opacity-100" : "opacity-0"
            }`}
            sizes="(max-width: 768px) 33vw, (max-width: 1024px) 25vw, (max-width: 1280px) 20vw, 16vw"
            unoptimized
            onLoad={() => setImageLoaded(true)}
          />
          {/* Fallback icon in case image fails to load */}
          <div className="absolute inset-0 flex items-center justify-center opacity-0">
            {getFileIcon(item.type, "h-8 w-8")}
          </div>
        </>
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          {getFileIcon(item.type, "h-8 w-8")}
        </div>
      )}
      <div className="absolute inset-0 bg-linear-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="absolute bottom-0 left-0 right-0 p-3">
          <p className="text-white text-sm font-medium truncate">{item.name}</p>
          <div className="flex items-center justify-between text-xs text-white/80 mt-1">
            <span>{format(item.date, "dd/MM/yyyy")}</span>
            <span>{item.size}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
