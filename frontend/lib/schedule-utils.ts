import type { Host, Group } from "./schedule-types";

export function targetsFor(type: "host" | "group", hosts: Host[], groups: Group[]) {
    return type === "host" ? hosts : groups;
}