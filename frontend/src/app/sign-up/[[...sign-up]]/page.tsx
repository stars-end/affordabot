import { SignUp } from "@clerk/nextjs";

export default function Page() {
    return (
        <div className="flex items-center justify-center min-h-screen bg-gray-50">
            <div className="p-4">
                <SignUp />
            </div>
        </div>
    );
}
