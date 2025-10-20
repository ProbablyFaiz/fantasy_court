import * as SelectPrimitive from "@radix-ui/react-select";
import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  children: ReactNode;
}

interface SelectItemProps {
  value: string;
  children: ReactNode;
}

export function Select({ value, onValueChange, children }: SelectProps) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger className="inline-flex items-center gap-1.5 text-sm text-foreground/80 pl-4 pr-2 py-2 border border-border rounded-sm bg-background hover:border-accent transition-colors cursor-pointer outline-none focus:border-accent">
        <SelectPrimitive.Value />
        <SelectPrimitive.Icon>
          <ChevronDown className="h-3.5 w-3.5 opacity-70" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content className="overflow-hidden bg-background border border-border rounded-sm shadow-lg">
          <SelectPrimitive.Viewport className="p-1">
            {children}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export function SelectItem({ value, children }: SelectItemProps) {
  return (
    <SelectPrimitive.Item
      value={value}
      className="relative flex items-center px-4 py-2 text-sm text-foreground/80 cursor-pointer outline-none select-none hover:bg-accent/10 focus:bg-accent/10 data-[state=checked]:bg-accent/15"
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}
