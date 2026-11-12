"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

type PasswordInputProps = {
  id: string;
  value: string;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  autoComplete: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
};

export function PasswordInput({ id, value, onChange, autoComplete, required, minLength, maxLength }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  return <div className="password-control">
    <input
      id={id}
      className="input password-input"
      type={visible ? "text" : "password"}
      autoComplete={autoComplete}
      required={required}
      minLength={minLength}
      maxLength={maxLength}
      value={value}
      onChange={onChange}
    />
    <button
      type="button"
      className="password-visibility"
      aria-label={visible ? "Hide password" : "Show password"}
      aria-pressed={visible}
      onClick={() => setVisible((current) => !current)}
    >{visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}</button>
  </div>;
}
